import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .models import HeritageSite, KmlUploadRecord, LandUseProjectApproval


HIGH_PROTECTION_LEVEL_CODES = {'GB', 'SB'}


def _local_tag(tag: str) -> str:
    return tag.split('}', 1)[-1] if '}' in tag else tag


def _parse_kml_coordinate_text(text: str) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    if not text:
        return points

    for token in str(text).replace('\n', ' ').replace('\t', ' ').split():
        parts = token.split(',')
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except (TypeError, ValueError):
            continue
        points.append((lon, lat))
    return points


def _points_equal(a: Tuple[float, float], b: Tuple[float, float], eps: float = 1e-8) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _close_ring(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    ring = list(points or [])
    if len(ring) < 3:
        return []
    if not _points_equal(ring[0], ring[-1]):
        ring.append(ring[0])
    if len(ring) < 4:
        return []
    return ring


def _extract_polygon_rings_from_kml_bytes(kml_bytes: bytes) -> List[List[Tuple[float, float]]]:
    """从KML中提取面环，兼容Polygon/MultiGeometry/GeometryCollection。"""
    rings: List[List[Tuple[float, float]]] = []
    root = ET.fromstring(kml_bytes)

    for node in root.iter():
        tag = _local_tag(node.tag)

        if tag == 'Polygon':
            for child in node.iter():
                if _local_tag(child.tag) != 'LinearRing':
                    continue
                coord_text = ''
                for sub in child.iter():
                    if _local_tag(sub.tag) == 'coordinates' and sub.text:
                        coord_text = sub.text
                        break
                closed = _close_ring(_parse_kml_coordinate_text(coord_text))
                if closed:
                    rings.append(closed)
            continue

        # 兼容以闭合线表示面的情况
        if tag in {'LinearRing', 'LineString'}:
            coord_text = ''
            for sub in node.iter():
                if _local_tag(sub.tag) == 'coordinates' and sub.text:
                    coord_text = sub.text
                    break
            points = _parse_kml_coordinate_text(coord_text)
            if len(points) < 3:
                continue
            if not _points_equal(points[0], points[-1]) and tag == 'LineString':
                continue
            closed = _close_ring(points)
            if closed:
                rings.append(closed)

    return rings


def _orientation(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, eps=1e-10) -> bool:
    if min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps:
        return abs(_orientation(a, b, p)) <= eps
    return False


def _segments_intersect(a1, a2, b1, b2) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if (o1 > 0 > o2 or o1 < 0 < o2) and (o3 > 0 > o4 or o3 < 0 < o4):
        return True

    return (
        _on_segment(a1, a2, b1)
        or _on_segment(a1, a2, b2)
        or _on_segment(b1, b2, a1)
        or _on_segment(b1, b2, a2)
    )


def _point_in_polygon(point: Tuple[float, float], ring: List[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    if len(ring) < 4:
        return False

    for idx in range(len(ring) - 1):
        x1, y1 = ring[idx]
        x2, y2 = ring[idx + 1]

        if _on_segment((x1, y1), (x2, y2), (x, y)):
            return True

        intersects = ((y1 > y) != (y2 > y))
        if intersects:
            cross_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x <= cross_x:
                inside = not inside

    return inside


def _polygon_intersects(a: List[Tuple[float, float]], b: List[Tuple[float, float]]) -> bool:
    if len(a) < 4 or len(b) < 4:
        return False

    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            if _segments_intersect(a[i], a[i + 1], b[j], b[j + 1]):
                return True

    return _point_in_polygon(a[0], b) or _point_in_polygon(b[0], a)


def _parse_zone_rings(zone_text: str) -> List[List[Tuple[float, float]]]:
    """解析HeritageSite中的保护范围/建控地带JSON。"""
    if not zone_text:
        return []

    try:
        parsed = json.loads(zone_text)
    except Exception:
        return []

    if not isinstance(parsed, list) or not parsed:
        return []

    # 结构1：[[lon,lat],[lon,lat],...]
    if isinstance(parsed[0], list) and len(parsed[0]) >= 2 and isinstance(parsed[0][0], (int, float, str)):
        ring = []
        for item in parsed:
            try:
                ring.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError, IndexError):
                continue
        closed = _close_ring(ring)
        return [closed] if closed else []

    # 结构2：[[[lon,lat],...], [[lon,lat],...], ...]
    rings: List[List[Tuple[float, float]]] = []
    for group in parsed:
        if not isinstance(group, list):
            continue
        ring = []
        for item in group:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            try:
                ring.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue
        closed = _close_ring(ring)
        if closed:
            rings.append(closed)

    return rings


DEFAULT_SPATIAL_THRESHOLD_M = 50


def sync_project_kml_record(project: LandUseProjectApproval, user=None) -> KmlUploadRecord:
    """把项目 KML 同步为一条 KML 叠加检查记录，使项目与独立叠加检查共用同一份数据。"""
    if not project.kml_file_path or not default_storage.exists(project.kml_file_path):
        raise ValueError('项目尚未上传KML文件')

    with default_storage.open(project.kml_file_path, 'rb') as fp:
        content = fp.read()

    filename = os.path.basename(project.kml_file_path)
    title = f'【项目】{project.project_name}'

    record = project.kml_record
    if record is None:
        record = KmlUploadRecord(
            title=title,
            uploaded_by=user if getattr(user, 'is_authenticated', False) else None,
            threshold_m=project.spatial_check_threshold_m or DEFAULT_SPATIAL_THRESHOLD_M,
        )
    else:
        record.title = title
        if record.source_file:
            record.source_file.delete(save=False)

    record.source_file.save(filename, ContentFile(content), save=False)
    record.save()

    if project.kml_record_id != record.id:
        project.kml_record = record
        project.save(update_fields=['kml_record', 'updated_at'])

    return record


def link_project_kml_record(project: LandUseProjectApproval, record: KmlUploadRecord) -> None:
    """把已有的 KML 叠加检查记录关联到项目，并同步项目侧 KML 路径。"""
    if not record.source_file:
        raise ValueError('该叠加检查记录没有可用的KML文件')

    changed_source = project.kml_record_id != record.id
    project.kml_record = record
    project.kml_file_path = record.source_file.name
    update_fields = ['kml_record', 'kml_file_path', 'updated_at']

    # 换了选址范围且流程尚未越过初步核查时，清空旧结论并退回待核验状态。
    if changed_source and project.status in {
        LandUseProjectApproval.STATUS_RECEIVED,
        LandUseProjectApproval.STATUS_PRELIM_SAFE,
        LandUseProjectApproval.STATUS_CHECK_OVERLAP,
    }:
        project.is_overlap_artifact = False
        project.overlapped_relics_info = []
        project.spatial_check_at = None
        project.spatial_feature_count = 0
        project.status = LandUseProjectApproval.STATUS_RECEIVED
        update_fields += [
            'is_overlap_artifact', 'overlapped_relics_info',
            'spatial_check_at', 'spatial_feature_count', 'status',
        ]

    project.save(update_fields=update_fields)


def _write_back_kml_record(record: KmlUploadRecord, threshold_m: int, features, conflicts) -> None:
    """把核验结果写回叠加检查记录，让 KML 管理页看到同一份结论。"""
    record.threshold_m = threshold_m
    record.feature_count = len(features)
    record.conflict_count = len(conflicts)
    record.report_json = json.dumps(
        {
            'threshold_m': threshold_m,
            'feature_count': len(features),
            'conflict_count': len(conflicts),
            'generated_at': timezone.now().isoformat(),
            'conflicts': conflicts,
        },
        ensure_ascii=False,
    )
    record.save(update_fields=['threshold_m', 'feature_count', 'conflict_count', 'report_json', 'updated_at'])


def verify_project_spatial_safety(project_id, threshold_m: int = None, user=None):
    """
    核心空间核验函数：
    - 读取项目已上传KML文件（并同步为 KML 叠加检查记录）
    - 直接调用 KML 叠加检查后端（特征解析 + 冲突分析）
    - 自动回写状态、重叠标记、重叠清单，以及叠加检查记录的冲突报告
    """
    project = LandUseProjectApproval.objects.filter(id=project_id).first()
    if not project:
        raise ValueError('项目不存在')
    if not project.kml_file_path:
        raise ValueError('项目尚未上传KML文件')
    if not default_storage.exists(project.kml_file_path):
        raise ValueError('KML文件不存在或已被移除')

    from . import views as legacy_views

    try:
        threshold = int(threshold_m or project.spatial_check_threshold_m or DEFAULT_SPATIAL_THRESHOLD_M)
    except (TypeError, ValueError):
        threshold = DEFAULT_SPATIAL_THRESHOLD_M
    threshold = max(1, min(5000, threshold))

    record = project.kml_record
    if record is None:
        record = sync_project_kml_record(project, user=user)

    with default_storage.open(project.kml_file_path, 'rb') as fp:
        content = fp.read()

    features = legacy_views._extract_features_from_upload(project.kml_file_path, content)
    if not features:
        raise ValueError('KML未识别到有效要素，请检查文件格式与坐标内容')

    conflicts = legacy_views._analyze_conflicts(features, threshold)

    level_label_map = {code: label for code, label in HeritageSite.LEVEL_CHOICES}
    overlaps = []
    for row in conflicts:
        site_level = (row.get('site_level') or '').strip()
        overlaps.append({
            'heritage_id': row.get('site_id'),
            'heritage_name': row.get('site_name') or '',
            'site_level': site_level,
            'site_level_label': level_label_map.get(site_level, site_level),
            'is_high_level_protected': site_level in HIGH_PROTECTION_LEVEL_CODES,
            'zone_type': row.get('relation') or '叠加冲突',
            'distance_m': row.get('distance_m'),
            'feature_name': row.get('feature_name') or '',
            'feature_type': row.get('feature_type') or '',
        })

    unique = []
    seen = set()
    for item in overlaps:
        key = (item.get('heritage_id'), item.get('zone_type'), item.get('feature_name'))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    has_high_level_overlap = any(item.get('is_high_level_protected') for item in unique)
    is_feasible_by_level = not has_high_level_overlap

    with transaction.atomic():
        project.is_overlap_artifact = bool(unique)
        project.overlapped_relics_info = unique
        project.spatial_check_at = timezone.now()
        project.spatial_check_threshold_m = threshold
        project.spatial_feature_count = len(features)
        project.status = (
            LandUseProjectApproval.STATUS_CHECK_OVERLAP
            if unique
            else LandUseProjectApproval.STATUS_PRELIM_SAFE
        )
        project.save(update_fields=[
            'is_overlap_artifact', 'overlapped_relics_info', 'status',
            'spatial_check_at', 'spatial_check_threshold_m', 'spatial_feature_count', 'updated_at',
        ])
        _write_back_kml_record(record, threshold, features, conflicts)

    return {
        'project_id': str(project.id),
        'is_overlap_artifact': bool(unique),
        'is_feasible_by_level': is_feasible_by_level,
        'status': project.status,
        'kml_record_id': record.id,
        'threshold_m': threshold,
        'feature_count': len(features),
        'conflict_count': len(conflicts),
        'overlapped_relics_info': unique,
    }


def build_project_media_path(project: LandUseProjectApproval, section: str, filename: str) -> str:
    """按年度/项目名自动归档，返回相对MEDIA_ROOT的路径。"""
    year = project.receive_date.year if project.receive_date else timezone.localdate().year
    safe_name = re.sub(r'[\\/:*?"<>|]+', '_', (project.project_name or '').strip())
    safe_name = safe_name[:80] if safe_name else f'project_{project.id}'
    base = os.path.join('projects', str(year), safe_name, section)
    return os.path.join(base, filename)


def _is_feasible_for_overlap(project: LandUseProjectApproval) -> bool:
    rows = project.overlapped_relics_info if isinstance(project.overlapped_relics_info, list) else []
    has_high_level = any((row or {}).get('site_level') in HIGH_PROTECTION_LEVEL_CODES for row in rows)
    return not has_high_level


def get_status_controls(status: str, project: LandUseProjectApproval = None) -> Dict[str, bool]:
    """前端按钮控制：基于状态机输出可用操作。"""
    feasible_overlap = _is_feasible_for_overlap(project) if project else False
    can_direct_reply = status == LandUseProjectApproval.STATUS_PRELIM_SAFE or (
        status == LandUseProjectApproval.STATUS_CHECK_OVERLAP and not feasible_overlap
    )

    is_overlap = bool(project.is_overlap_artifact) if project else False

    return {
        'upload_kml': status == LandUseProjectApproval.STATUS_RECEIVED,
        'upload_misc_zip': True,
        'verify_spatial': status == LandUseProjectApproval.STATUS_RECEIVED,
        # 市县联合实地勘查：不涉及/涉及且可行两条分支都需先完成，与流程文档步骤4对应。
        'upload_field_photos': status in {
            LandUseProjectApproval.STATUS_PRELIM_SAFE,
            LandUseProjectApproval.STATUS_CHECK_OVERLAP,
            LandUseProjectApproval.STATUS_FIELD_DONE,
        },
        'input_city_reply': status == LandUseProjectApproval.STATUS_CITY_REVIEWING or can_direct_reply,
        'submit_archaeology': status in {
            LandUseProjectApproval.STATUS_CHECK_OVERLAP,
            LandUseProjectApproval.STATUS_FIELD_DONE,
            LandUseProjectApproval.STATUS_CITY_REVIEWING,
        } and feasible_overlap,
        'upload_archaeology_report': status == LandUseProjectApproval.STATUS_ARCHAEOLOGY,
        # 坎儿井保护加固方案与水利部门意见：项目确认涉及文物后即可录入，专项流转前需补齐。
        'update_kanerjing_info': is_overlap and status not in {
            LandUseProjectApproval.STATUS_ARCHIVED,
        },
        'upload_kanerjing_plan': is_overlap and status not in {
            LandUseProjectApproval.STATUS_ARCHIVED,
        },
        'close_archive': status == LandUseProjectApproval.STATUS_REPLY_RECEIVED,
        # 保护措施落实核实：仅涉及文物的项目在办结归档前需要确认。
        'confirm_protection_measures': is_overlap and status == LandUseProjectApproval.STATUS_REPLY_RECEIVED,
    }


def apply_workflow_action(project: LandUseProjectApproval, action: str, payload: Dict):
    """业务流转强控：校验当前状态与必填字段后再跳转。"""
    if action == 'complete_field_check':
        # 无论初审结果是否涉及文物，均需先完成市县联合实地勘查（流程文档步骤4）。
        if project.status not in {
            LandUseProjectApproval.STATUS_PRELIM_SAFE,
            LandUseProjectApproval.STATUS_CHECK_OVERLAP,
        }:
            raise ValueError('当前状态不允许提交现场勘查完成')
        if not payload.get('field_check_date'):
            raise ValueError('请先填写现场勘查日期')
        if project.field_photos.count() == 0:
            raise ValueError('请先上传现场照片后再提交')
        project.field_check_date = payload.get('field_check_date')
        project.status = LandUseProjectApproval.STATUS_FIELD_DONE

    elif action == 'submit_city_request':
        if project.status not in {
            LandUseProjectApproval.STATUS_FIELD_DONE,
            LandUseProjectApproval.STATUS_CHECK_OVERLAP,
        }:
            raise ValueError('当前状态不允许录入县局请示')
        if project.status == LandUseProjectApproval.STATUS_CHECK_OVERLAP and not _is_feasible_for_overlap(project):
            raise ValueError('当前项目涉及自治区及以上级别文物，判定为不可行，不得进入考古上报流程')
        req_num = (payload.get('shanshan_request_num') or '').strip()
        if not re.match(r'^鄯文旅字-\d{4}-\d+号$', req_num):
            raise ValueError('县局请示文号格式错误，应为：鄯文旅字-2026-xx号')
        project.shanshan_request_num = req_num
        project.status = LandUseProjectApproval.STATUS_CITY_REVIEWING

    elif action == 'record_city_reply':
        if project.status == LandUseProjectApproval.STATUS_CITY_REVIEWING:
            city_reply_num = (payload.get('city_reply_num') or '').strip()
            if not city_reply_num:
                raise ValueError('市局复函号不能为空')
            project.city_reply_num = city_reply_num
        elif project.status == LandUseProjectApproval.STATUS_PRELIM_SAFE:
            final_reply = (payload.get('final_reply_to_company') or '').strip()
            if not final_reply:
                raise ValueError('不涉及文物时，需填写给企业最终复函号')
            project.final_reply_to_company = final_reply
        elif project.status == LandUseProjectApproval.STATUS_CHECK_OVERLAP and not _is_feasible_for_overlap(project):
            final_reply = (payload.get('final_reply_to_company') or '').strip()
            if not final_reply:
                raise ValueError('项目不可行时，需填写给企业最终复函号')
            project.final_reply_to_company = final_reply
        else:
            raise ValueError('当前状态不允许录入复函结果')
        project.status = LandUseProjectApproval.STATUS_REPLY_RECEIVED

    elif action == 'submit_archaeology_request':
        if project.status not in {
            LandUseProjectApproval.STATUS_CHECK_OVERLAP,
            LandUseProjectApproval.STATUS_FIELD_DONE,
            LandUseProjectApproval.STATUS_CITY_REVIEWING,
        }:
            raise ValueError('当前状态不允许发起考古流转')
        if project.is_overlap_artifact and not _is_feasible_for_overlap(project):
            raise ValueError('当前项目涉及自治区及以上级别文物，判定为不可行，不得进入考古流转')
        if project.involves_kanerjing:
            if not project.kanerjing_protection_plan_path:
                raise ValueError('涉及坎儿井时，需先上传坎儿井保护加固方案')
            if not project.water_department_opinion.strip():
                raise ValueError('涉及坎儿井时，需先征求并录入水利部门意见')
        archaeology_request_num = (payload.get('archaeology_request_num') or '').strip()
        if not archaeology_request_num:
            raise ValueError('考古请示文号不能为空')
        project.archaeology_request_num = archaeology_request_num
        project.status = LandUseProjectApproval.STATUS_ARCHAEOLOGY

    elif action == 'record_archaeology_reply':
        if project.status != LandUseProjectApproval.STATUS_ARCHAEOLOGY:
            raise ValueError('当前状态不允许录入考古与批复结果')
        region_approval_num = (payload.get('region_approval_num') or '').strip()
        city_final_reply_num = (payload.get('city_final_reply_num') or '').strip()
        if not project.archaeology_report_path:
            raise ValueError('请先上传自治区考古研究所PDF报告')
        if not region_approval_num:
            raise ValueError('自治区文物局批复文号不能为空')
        if not city_final_reply_num:
            raise ValueError('市文物局复函文号不能为空')
        project.region_approval_num = region_approval_num
        project.city_final_reply_num = city_final_reply_num
        # 依法需报国务院文物行政部门审批/审核/征求意见的，逐级报审需补齐批复文号（流程文档步骤8）。
        if 'requires_state_council_approval' in payload:
            project.requires_state_council_approval = bool(payload.get('requires_state_council_approval'))
        if project.requires_state_council_approval:
            state_council_approval_num = (
                payload.get('state_council_approval_num') or project.state_council_approval_num or ''
            ).strip()
            if not state_council_approval_num:
                raise ValueError('已标记需报国务院文物行政部门，国务院批复文号不能为空')
            project.state_council_approval_num = state_council_approval_num
        project.status = LandUseProjectApproval.STATUS_REPLY_RECEIVED

    elif action == 'archive_case':
        if project.status != LandUseProjectApproval.STATUS_REPLY_RECEIVED:
            raise ValueError('当前状态不允许办结归档')
        final_reply = (payload.get('final_reply_to_company') or '').strip()
        if not final_reply:
            raise ValueError('最终复函号不能为空')
        # 涉及文物的项目需先核实原址保护/迁移保护/坎儿井加固等保护措施已落实（流程文档步骤9）。
        if project.is_overlap_artifact and not project.protection_measures_confirmed:
            raise ValueError('涉及文物的项目需先核实保护措施落实情况，再办结归档')
        project.final_reply_to_company = final_reply
        project.status = LandUseProjectApproval.STATUS_ARCHIVED

    elif action == 'update_extra_info':
        # 不涉及状态跳转的辅助信息录入：坎儿井方案/水利意见/国务院报审标记/保护措施说明等。
        if 'involves_kanerjing' in payload:
            project.involves_kanerjing = bool(payload.get('involves_kanerjing'))
        if 'water_department_opinion' in payload:
            project.water_department_opinion = (payload.get('water_department_opinion') or '').strip()
        if 'requires_state_council_approval' in payload:
            project.requires_state_council_approval = bool(payload.get('requires_state_council_approval'))
        if 'state_council_approval_num' in payload:
            project.state_council_approval_num = (payload.get('state_council_approval_num') or '').strip()
        if 'protection_measures_note' in payload:
            project.protection_measures_note = (payload.get('protection_measures_note') or '').strip()
        if 'protection_measures_confirmed' in payload:
            confirmed = bool(payload.get('protection_measures_confirmed'))
            if confirmed and not project.protection_measures_note.strip():
                raise ValueError('确认保护措施落实前，请先填写落实情况说明')
            project.protection_measures_confirmed = confirmed

    else:
        raise ValueError('不支持的流程动作')

    project.save()
    return {
        'project_id': str(project.id),
        'status': project.status,
        'status_label': project.get_status_display(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 流程向导：把状态机翻译成「当前在哪一步、现在能做什么、还缺什么」
# ──────────────────────────────────────────────────────────────────────────────

PATH_PENDING = 'PENDING'
PATH_DIRECT_REPLY = 'DIRECT_REPLY'
PATH_ARCHAEOLOGY = 'ARCHAEOLOGY_FLOW'

WORKFLOW_STEPS = [
    ('receive', '收文登记', '接收项目方查询函，登记项目名称、建设内容与选址范围资料'),
    ('precheck', '初步核查', '将项目选址范围与不可移动文物、保护范围、建控地带矢量数据叠加比对'),
    ('field_check', '联合实地勘查', '市、县文物行政部门赴现场核实选址与文物实际位置及影响'),
    ('city_review', '上报市局与回复意见', '报送县局请示，等待市文物行政部门反馈勘查意见'),
    ('archaeology', '专项保护与逐级报审', '考古调查勘探、影响评估、保护方案编制，并按权限逐级报审'),
    ('reply', '出具复函', '依据市级回复向项目方出具《涉及文物保护工作意见的复函》'),
    ('archive', '办结归档', '核实保护措施落实情况，出具最终意见并归档'),
]

_STATUS_TO_STEP = {
    LandUseProjectApproval.STATUS_RECEIVED: 'receive',
    LandUseProjectApproval.STATUS_PRELIM_SAFE: 'field_check',
    LandUseProjectApproval.STATUS_CHECK_OVERLAP: 'field_check',
    LandUseProjectApproval.STATUS_FIELD_DONE: 'city_review',
    LandUseProjectApproval.STATUS_CITY_REVIEWING: 'city_review',
    LandUseProjectApproval.STATUS_ARCHAEOLOGY: 'archaeology',
    LandUseProjectApproval.STATUS_REPLY_RECEIVED: 'archive',
    LandUseProjectApproval.STATUS_ARCHIVED: 'archive',
}


def get_current_step_key(project: LandUseProjectApproval) -> str:
    return _STATUS_TO_STEP.get(project.status, 'receive')


def _field(name, label, field_type='text', required=True, value=None, placeholder='', hint=''):
    return {
        'name': name,
        'label': label,
        'type': field_type,
        'required': required,
        'value': value if value is not None else ('' if field_type != 'checkbox' else False),
        'placeholder': placeholder,
        'hint': hint,
    }


def resolve_workflow_path(project: LandUseProjectApproval) -> Tuple[str, str]:
    """返回 (分支编码, 分支说明)。"""
    if project.spatial_check_at is None and not project.is_overlap_artifact:
        return PATH_PENDING, '尚未完成初步核查，请先上传选址KML并执行叠加核验。'
    if not project.is_overlap_artifact:
        return PATH_DIRECT_REPLY, '初步核查未涉及已登记文物：报送上行文申请联合现场勘查，之后直接出具复函。'
    if _is_feasible_for_overlap(project):
        return PATH_ARCHAEOLOGY, '涉及文物但未触及自治区及以上级别：先提出避让或优化方案意见，无法避让的进入专项保护程序。'
    return PATH_DIRECT_REPLY, '涉及自治区及以上级别文物：应优先要求避让或调整选址，据此出具不予同意的复函。'


def _step_states(project: LandUseProjectApproval, path: str) -> List[Dict]:
    current_key = get_current_step_key(project)
    skip_archaeology = path != PATH_ARCHAEOLOGY

    keys = [key for key, _label, _desc in WORKFLOW_STEPS]
    current_index = keys.index(current_key) if current_key in keys else 0

    steps = []
    for index, (key, title, desc) in enumerate(WORKFLOW_STEPS):
        if key == 'archaeology' and skip_archaeology:
            state = 'skipped'
        elif project.status == LandUseProjectApproval.STATUS_ARCHIVED:
            state = 'done'
        elif index < current_index:
            state = 'done'
        elif index == current_index:
            state = 'current'
        else:
            state = 'pending'
        steps.append({'key': key, 'title': title, 'description': desc, 'state': state})
    return steps


def _spatial_todos(project: LandUseProjectApproval) -> List[Dict]:
    blockers = []
    if not project.kml_file_path:
        blockers.append('请先在「附件与文档」上传项目选址KML/KMZ文件')

    return [{
        'action': 'verify_spatial_safety',
        'kind': 'spatial',
        'label': '执行叠加核验',
        'description': '把项目选址范围与文物本体、保护范围、建控地带做叠加比对，自动判定是否涉及文物。',
        'enabled': not blockers,
        'blockers': blockers,
        'fields': [
            _field('threshold_m', '缓冲阈值(米)', 'number', required=False,
                   value=project.spatial_check_threshold_m or DEFAULT_SPATIAL_THRESHOLD_M,
                   hint='项目要素与文物点距离小于该值即计入冲突'),
        ],
    }]


def build_workflow_todos(project: LandUseProjectApproval, path: str) -> List[Dict]:
    """按当前状态输出可执行动作，含禁用原因与所需填写字段。"""
    status = project.status
    todos = []

    if status == LandUseProjectApproval.STATUS_RECEIVED:
        return _spatial_todos(project)

    if status in {LandUseProjectApproval.STATUS_PRELIM_SAFE, LandUseProjectApproval.STATUS_CHECK_OVERLAP}:
        todos.extend(_spatial_todos(project))
        for item in todos:
            item['label'] = '重新执行叠加核验'
            item['description'] = '选址范围或阈值调整后，可重新核验并刷新涉及文物清单。'

        photo_blockers = [] if project.field_photos.count() else ['请先上传至少一张现场勘查照片']
        todos.append({
            'action': 'complete_field_check',
            'kind': 'workflow',
            'label': '提交联合实地勘查完成',
            'description': '市、县联合现场勘查完成后登记勘查日期，进入上报市局环节。',
            'enabled': not photo_blockers,
            'blockers': photo_blockers,
            'fields': [
                _field('field_check_date', '现场勘查日期', 'date',
                       value=project.field_check_date.isoformat() if project.field_check_date else ''),
            ],
        })

        if path == PATH_DIRECT_REPLY:
            todos.append({
                'action': 'record_city_reply',
                'kind': 'workflow',
                'label': '直接出具复函',
                'description': (
                    '未涉及文物，可直接向项目方出具标准复函。'
                    if not project.is_overlap_artifact
                    else '涉及高等级文物且无法避让，向项目方出具不予同意的复函。'
                ),
                'enabled': True,
                'blockers': [],
                'fields': [
                    _field('final_reply_to_company', '给项目方复函号', value=project.final_reply_to_company),
                ],
            })
        return todos

    if status == LandUseProjectApproval.STATUS_FIELD_DONE:
        todos.append({
            'action': 'submit_city_request',
            'kind': 'workflow',
            'label': '报送县局请示',
            'description': '登记县局请示文号并上报市文物行政部门，等待回复意见。',
            'enabled': True,
            'blockers': [],
            'fields': [
                _field('shanshan_request_num', '县局请示文号',
                       value=project.shanshan_request_num,
                       placeholder=LandUseProjectApproval.suggest_next_shanshan_num(),
                       hint='格式：鄯文旅字-2026-xx号'),
            ],
        })

    if status == LandUseProjectApproval.STATUS_CITY_REVIEWING:
        todos.append({
            'action': 'record_city_reply',
            'kind': 'workflow',
            'label': '录入市局回复意见',
            'description': '登记市文物行政部门的复函文号，据此向项目方出具复函。',
            'enabled': True,
            'blockers': [],
            'fields': [
                _field('city_reply_num', '市局复函文号', value=project.city_reply_num),
            ],
        })

    if status in {
        LandUseProjectApproval.STATUS_FIELD_DONE,
        LandUseProjectApproval.STATUS_CITY_REVIEWING,
    } and path == PATH_ARCHAEOLOGY:
        blockers = []
        if project.involves_kanerjing:
            if not project.kanerjing_protection_plan_path:
                blockers.append('涉及坎儿井：请先上传坎儿井保护加固方案PDF')
            if not project.water_department_opinion.strip():
                blockers.append('涉及坎儿井：请先录入水利部门意见')
        todos.append({
            'action': 'submit_archaeology_request',
            'kind': 'workflow',
            'label': '发起专项保护程序',
            'description': '无法避让时，依法开展考古调查勘探、文物影响评估与保护方案编制。',
            'enabled': not blockers,
            'blockers': blockers,
            'fields': [
                _field('archaeology_request_num', '考古请示文号', value=project.archaeology_request_num),
            ],
        })

    if status == LandUseProjectApproval.STATUS_ARCHAEOLOGY:
        blockers = [] if project.archaeology_report_path else ['请先上传自治区考古研究所调查报告PDF']
        todos.append({
            'action': 'record_archaeology_reply',
            'kind': 'workflow',
            'label': '录入考古与逐级报审结果',
            'description': '登记自治区文物局批复与市文物局最终复函；依法需报国务院的一并登记。',
            'enabled': not blockers,
            'blockers': blockers,
            'fields': [
                _field('region_approval_num', '自治区文物局批复文号', value=project.region_approval_num),
                _field('city_final_reply_num', '市文物局最终复函号', value=project.city_final_reply_num),
                _field('requires_state_council_approval', '需报国务院文物行政部门', 'checkbox',
                       required=False, value=project.requires_state_council_approval),
                _field('state_council_approval_num', '国务院批复文号', required=False,
                       value=project.state_council_approval_num,
                       hint='仅在勾选“需报国务院文物行政部门”时必填'),
            ],
        })

    if status == LandUseProjectApproval.STATUS_REPLY_RECEIVED:
        blockers = []
        if project.is_overlap_artifact and not project.protection_measures_confirmed:
            blockers.append('涉及文物：请先在下方登记并确认保护措施落实情况')
        todos.append({
            'action': 'archive_case',
            'kind': 'workflow',
            'label': '出具最终意见并归档',
            'description': '核实保护措施落实到位后，向项目方出具最终涉及文物保护工作意见并结案。',
            'enabled': not blockers,
            'blockers': blockers,
            'fields': [
                _field('final_reply_to_company', '给项目方最终复函号', value=project.final_reply_to_company),
            ],
        })

    return todos


def build_extra_info_form(project: LandUseProjectApproval) -> Dict:
    """随时可编辑的辅助信息：坎儿井专项、逐级报审、保护措施落实。"""
    return {
        'action': 'update_extra_info',
        'kind': 'workflow',
        'label': '保存补充信息',
        'fields': [
            _field('involves_kanerjing', '涉及坎儿井', 'checkbox', required=False,
                   value=project.involves_kanerjing,
                   hint='涉及坎儿井需编制保护加固方案并征求水利部门意见'),
            _field('water_department_opinion', '水利部门意见', 'textarea', required=False,
                   value=project.water_department_opinion),
            _field('requires_state_council_approval', '需报国务院文物行政部门', 'checkbox',
                   required=False, value=project.requires_state_council_approval),
            _field('state_council_approval_num', '国务院批复文号', required=False,
                   value=project.state_council_approval_num),
            _field('protection_measures_note', '保护措施落实情况说明', 'textarea', required=False,
                   value=project.protection_measures_note,
                   hint='原址保护 / 迁移保护 / 考古调查勘探 / 坎儿井加固等'),
            _field('protection_measures_confirmed', '保护措施已核实落实', 'checkbox',
                   required=False, value=project.protection_measures_confirmed),
        ],
    }


def build_workflow_guide(project: LandUseProjectApproval) -> Dict:
    path, advice = resolve_workflow_path(project)
    return {
        'path': path,
        'path_label': {
            PATH_PENDING: '待核查',
            PATH_DIRECT_REPLY: '直接复函',
            PATH_ARCHAEOLOGY: '专项保护流程',
        }.get(path, path),
        'advice': advice,
        'current_step': get_current_step_key(project),
        'steps': _step_states(project, path),
        'todos': build_workflow_todos(project, path),
        'extra_info_form': build_extra_info_form(project),
        'is_archived': project.status == LandUseProjectApproval.STATUS_ARCHIVED,
    }
