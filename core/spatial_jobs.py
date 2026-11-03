"""项目空间核验后台任务。

大型矢量文件的叠加分析是纯 CPU 计算，可能超过网关/浏览器的请求超时，
因此改为后台线程执行，前端通过任务ID轮询进度。任务状态保存为临时 JSON 文件，
这样多个 gunicorn worker 之间无需共享内存，也不需要新增数据库迁移。
"""
import json
import logging
import os
import tempfile
import threading
import time
import uuid

logger = logging.getLogger(__name__)

JOB_DIR = os.path.join(tempfile.gettempdir(), 'heritage_spatial_jobs')
# 任务长时间没有进度更新（例如 worker 被回收）时视为已中断。
STALE_SECONDS = 15 * 60
RETENTION_SECONDS = 24 * 3600
ACTIVE_STATUSES = {'queued', 'running'}

_write_lock = threading.Lock()


def _job_path(job_id):
    return os.path.join(JOB_DIR, f'{job_id}.json')


def _write_job(job):
    os.makedirs(JOB_DIR, exist_ok=True)
    job['updated_at'] = time.time()
    path = _job_path(job['job_id'])
    tmp_path = f'{path}.{uuid.uuid4().hex}.tmp'
    with _write_lock:
        with open(tmp_path, 'w', encoding='utf-8') as fp:
            json.dump(job, fp, ensure_ascii=False)
        os.replace(tmp_path, path)


def _read_job(path):
    try:
        with open(path, 'r', encoding='utf-8') as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return None


def _normalize_stale(job):
    if job and job.get('status') in ACTIVE_STATUSES and time.time() - job.get('updated_at', 0) > STALE_SECONDS:
        job['status'] = 'failed'
        job['error'] = '核验任务已中断，请重新执行'
    return job


def get_job(job_id):
    try:
        job_id = str(uuid.UUID(str(job_id)))
    except ValueError:
        return None
    return _normalize_stale(_read_job(_job_path(job_id)))


def _cleanup_old_jobs():
    try:
        names = os.listdir(JOB_DIR)
    except OSError:
        return
    now = time.time()
    for name in names:
        path = os.path.join(JOB_DIR, name)
        try:
            if now - os.path.getmtime(path) > RETENTION_SECONDS:
                os.remove(path)
        except OSError:
            continue


def find_active_job(project_id, preliminary):
    try:
        names = os.listdir(JOB_DIR)
    except OSError:
        return None
    for name in names:
        if not name.endswith('.json'):
            continue
        job = _normalize_stale(_read_job(os.path.join(JOB_DIR, name)))
        if (
            job
            and job.get('status') in ACTIVE_STATUSES
            and job.get('project_id') == str(project_id)
            and bool(job.get('preliminary')) == bool(preliminary)
        ):
            return job
    return None


def public_job(job):
    return {
        'job_id': job['job_id'],
        'project_id': job['project_id'],
        'preliminary': bool(job.get('preliminary')),
        'status': job['status'],
        'stage': job.get('stage', ''),
        'processed': job.get('processed', 0),
        'total': job.get('total', 0),
        'result': job.get('result'),
        'error': job.get('error', ''),
        'error_status': job.get('error_status'),
    }


def _run_job(job, threshold_m, user):
    from django.db import close_old_connections

    from . import views as legacy_views
    from .land_project_services import verify_preliminary_spatial_safety, verify_project_spatial_safety
    from .models import LandUseProjectApproval

    last_write = 0.0

    def progress(stage, processed=0, total=0):
        nonlocal last_write
        now = time.monotonic()
        job.update(stage=stage, processed=processed, total=total)
        # 限制写盘频率，避免进度回调拖慢分析。
        if now - last_write >= 0.5 or processed >= total:
            last_write = now
            _write_job(job)

    try:
        job['status'] = 'running'
        _write_job(job)

        project = LandUseProjectApproval.objects.filter(id=job['project_id']).first()
        status_before = project.status if project else ''
        verify = verify_preliminary_spatial_safety if job['preliminary'] else verify_project_spatial_safety
        result = verify(job['project_id'], threshold_m=threshold_m, user=user, progress_callback=progress)

        if project:
            legacy_views._record_land_project_operation(
                project=project,
                user=user,
                action='verify_preliminary_spatial' if job['preliminary'] else 'verify_spatial_safety',
                payload={
                    'is_overlap_artifact': result.get('is_overlap_artifact', False),
                    'overlapped_count': len(result.get('overlapped_relics_info') or []),
                    'threshold_m': result.get('threshold_m'),
                    'feature_count': result.get('feature_count'),
                },
                status_before=status_before,
                status_after=result.get('status', status_before),
            )
        job.update(status='succeeded', result=result, stage='done')
    except ValueError as exc:
        job.update(status='failed', error=str(exc), error_status=400)
    except Exception:
        logger.exception('项目空间核验后台任务失败: project_id=%s', job['project_id'])
        job.update(status='failed', error='空间核验失败，请检查KML与空间数据', error_status=500)
    finally:
        _write_job(job)
        close_old_connections()


def start_job(project_id, preliminary, threshold_m, user):
    """启动后台核验；同一项目同一类型已有进行中的任务时直接复用，避免重复提交。"""
    existing = find_active_job(project_id, preliminary)
    if existing:
        return existing

    _cleanup_old_jobs()
    job = {
        'job_id': str(uuid.uuid4()),
        'project_id': str(project_id),
        'preliminary': bool(preliminary),
        'status': 'queued',
        'stage': 'queued',
        'processed': 0,
        'total': 0,
        'result': None,
        'error': '',
        'error_status': None,
        'created_at': time.time(),
    }
    _write_job(job)
    threading.Thread(
        target=_run_job,
        args=(job, threshold_m, user),
        name=f'spatial-verify-{job["job_id"][:8]}',
        daemon=True,
    ).start()
    return job
