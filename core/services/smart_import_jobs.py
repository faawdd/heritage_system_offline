import json
import logging
import os
import tempfile
import threading
import time
import uuid

from core.services.project_import_service import analyze_project_files


logger = logging.getLogger(__name__)

JOB_DIR = os.path.join(tempfile.gettempdir(), 'heritage_smart_import_jobs')
ACTIVE_STATUSES = {'queued', 'running'}
STALE_SECONDS = 15 * 60
RETENTION_SECONDS = 24 * 3600
_write_lock = threading.Lock()


def _job_path(job_id):
    return os.path.join(JOB_DIR, f'{job_id}.json')


def _write_job(job):
    os.makedirs(JOB_DIR, exist_ok=True)
    job['updated_at'] = time.time()
    path = _job_path(job['job_id'])
    temporary_path = f'{path}.{uuid.uuid4().hex}.tmp'
    with _write_lock:
        with open(temporary_path, 'w', encoding='utf-8') as file_object:
            json.dump(job, file_object, ensure_ascii=False)
        os.replace(temporary_path, path)


def _read_job(path):
    try:
        with open(path, 'r', encoding='utf-8') as file_object:
            return json.load(file_object)
    except (OSError, ValueError):
        return None


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


def _normalize_stale(job):
    if job and job.get('status') in ACTIVE_STATUSES and time.time() - job.get('updated_at', 0) > STALE_SECONDS:
        job.update(
            status='failed',
            error='AI 识别任务已中断，请重新上传并执行识别',
            error_status=504,
        )
    return job


def get_job(job_id):
    try:
        normalized_id = str(uuid.UUID(str(job_id)))
    except ValueError:
        return None
    return _normalize_stale(_read_job(_job_path(normalized_id)))


def public_job(job):
    return {
        'job_id': job['job_id'],
        'status': job['status'],
        'stage': job.get('stage', ''),
        'result': job.get('result'),
        'error': job.get('error', ''),
        'error_status': job.get('error_status'),
    }


def _run_job(job, files):
    from django.db import close_old_connections

    try:
        close_old_connections()
        job.update(status='running', stage='analyzing')
        _write_job(job)
        result = analyze_project_files(files)
        job.update(status='succeeded', stage='done', result=result)
    except ValueError as exc:
        job.update(status='failed', error=str(exc), error_status=400)
    except Exception:
        logger.exception('AI 智能项目识别后台任务失败: job_id=%s', job['job_id'])
        job.update(
            status='failed',
            error='AI 识别失败，请检查 AI 服务配置或稍后重试',
            error_status=500,
        )
    finally:
        _write_job(job)
        close_old_connections()


def start_job(files):
    _cleanup_old_jobs()
    job = {
        'job_id': str(uuid.uuid4()),
        'status': 'queued',
        'stage': 'queued',
        'result': None,
        'error': '',
        'error_status': None,
        'created_at': time.time(),
    }
    _write_job(job)
    threading.Thread(
        target=_run_job,
        args=(job, files),
        name=f'smart-import-{job["job_id"][:8]}',
        daemon=True,
    ).start()
    return job
