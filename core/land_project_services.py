import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .models import HeritageSite, LandUseProjectApproval


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


def verify_project_spatial_safety(project_id):
    """
    核心空间核验函数：
    - 读取项目KML
    - 与不可移动文物保护范围/建控地带做相交测试
    - 自动回写状态、重叠标记与重叠清单
    """
    project = LandUseProjectApproval.objects.filter(id=project_id).first()
    if not project:
        raise ValueError('项目不存在')
    if not project.kml_file_path:
        raise ValueError('项目尚未上传KML文件')
    if not default_storage.exists(project.kml_file_path):
        raise ValueError('KML文件不存在或已被移除')

    with default_storage.open(project.kml_file_path, 'rb') as fp:
        project_rings = _extract_polygon_rings_from_kml_bytes(fp.read())

    if not project_rings:
        raise ValueError('KML未识别到有效面数据，请检查文件是否为面要素')

    overlaps = []
    for site in HeritageSite.objects.only('id', 'name', 'protection_zone', 'control_zone'):
        for zone_name, zone_text in (
            ('保护范围', site.protection_zone),
            ('建控地带', site.control_zone),
        ):
            site_rings = _parse_zone_rings(zone_text)
            if not site_rings:
                continue

            hit = False
            for project_ring in project_rings:
                if hit:
                    break
                for site_ring in site_rings:
                    if _polygon_intersects(project_ring, site_ring):
                        hit = True
                        break

            if hit:
                overlaps.append({
                    'heritage_id': site.id,
                    'heritage_name': site.name,
                    'zone_type': zone_name,
                })

    unique = []
    seen = set()
    for item in overlaps:
        key = (item['heritage_id'], item['zone_type'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    with transaction.atomic():
        project.is_overlap_artifact = bool(unique)
        project.overlapped_relics_info = unique
        project.status = (
            LandUseProjectApproval.STATUS_CHECK_OVERLAP
            if unique
            else LandUseProjectApproval.STATUS_PRELIM_SAFE
        )
        project.save(update_fields=['is_overlap_artifact', 'overlapped_relics_info', 'status', 'updated_at'])

    return {
        'project_id': str(project.id),
        'is_overlap_artifact': bool(unique),
        'status': project.status,
        'overlapped_relics_info': unique,
    }


def build_project_media_path(project: LandUseProjectApproval, section: str, filename: str) -> str:
    """按年度/项目名自动归档，返回相对MEDIA_ROOT的路径。"""
    year = project.receive_date.year if project.receive_date else timezone.localdate().year
    safe_name = re.sub(r'[\\/:*?"<>|]+', '_', (project.project_name or '').strip())
    safe_name = safe_name[:80] if safe_name else f'project_{project.id}'
    base = os.path.join('projects', str(year), safe_name, section)
    return os.path.join(base, filename)


def get_status_controls(status: str) -> Dict[str, bool]:
    """前端按钮控制：基于状态机输出可用操作。"""
    return {
        'upload_kml': status == LandUseProjectApproval.STATUS_RECEIVED,
        'verify_spatial': status == LandUseProjectApproval.STATUS_RECEIVED,
        'upload_field_photos': status in {
            LandUseProjectApproval.STATUS_PRELIM_SAFE,
            LandUseProjectApproval.STATUS_FIELD_DONE,
        },
        'input_city_reply': status == LandUseProjectApproval.STATUS_CITY_REVIEWING,
        'submit_archaeology': status == LandUseProjectApproval.STATUS_CHECK_OVERLAP,
        'upload_archaeology_report': status == LandUseProjectApproval.STATUS_ARCHAEOLOGY,
        'close_archive': status == LandUseProjectApproval.STATUS_REPLY_RECEIVED,
    }


def apply_workflow_action(project: LandUseProjectApproval, action: str, payload: Dict):
    """业务流转强控：校验当前状态与必填字段后再跳转。"""
    if action == 'complete_field_check':
        if project.status != LandUseProjectApproval.STATUS_PRELIM_SAFE:
            raise ValueError('当前状态不允许提交现场勘查完成')
        if not payload.get('field_check_date'):
            raise ValueError('请先填写现场勘查日期')
        if project.field_photos.count() == 0:
            raise ValueError('请先上传现场照片后再提交')
        project.field_check_date = payload.get('field_check_date')
        project.status = LandUseProjectApproval.STATUS_FIELD_DONE

    elif action == 'submit_city_request':
        if project.status != LandUseProjectApproval.STATUS_FIELD_DONE:
            raise ValueError('当前状态不允许录入县局请示')
        req_num = (payload.get('shanshan_request_num') or '').strip()
        if not re.match(r'^鄯文旅字-\d{4}-\d+号$', req_num):
            raise ValueError('县局请示文号格式错误，应为：鄯文旅字-2026-xx号')
        project.shanshan_request_num = req_num
        project.status = LandUseProjectApproval.STATUS_CITY_REVIEWING

    elif action == 'record_city_reply':
        if project.status != LandUseProjectApproval.STATUS_CITY_REVIEWING:
            raise ValueError('当前状态不允许录入市局复函')
        city_reply_num = (payload.get('city_reply_num') or '').strip()
        if not city_reply_num:
            raise ValueError('市局复函号不能为空')
        project.city_reply_num = city_reply_num
        project.status = LandUseProjectApproval.STATUS_REPLY_RECEIVED

    elif action == 'submit_archaeology_request':
        if project.status != LandUseProjectApproval.STATUS_CHECK_OVERLAP:
            raise ValueError('当前状态不允许发起考古流转')
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
        project.status = LandUseProjectApproval.STATUS_REPLY_RECEIVED

    elif action == 'archive_case':
        if project.status != LandUseProjectApproval.STATUS_REPLY_RECEIVED:
            raise ValueError('当前状态不允许办结归档')
        final_reply = (payload.get('final_reply_to_company') or '').strip()
        if not final_reply:
            raise ValueError('最终复函号不能为空')
        project.final_reply_to_company = final_reply
        project.status = LandUseProjectApproval.STATUS_ARCHIVED

    else:
        raise ValueError('不支持的流程动作')

    project.save()
    return {
        'project_id': str(project.id),
        'status': project.status,
        'status_label': project.get_status_display(),
    }
