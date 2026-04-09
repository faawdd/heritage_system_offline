# core/views.py
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from .models import HeritageSite, InspectionRecord, ProjectAudit, Coordinate, KmlUploadRecord
from .ovkml_converter import parse_ovkml, build_csv_outputs
import base64
import hashlib
import hmac
import json
import csv
from urllib.parse import quote
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, login as auth_login
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.conf import settings
from docxtpl import DocxTemplate
import os
import io
import zipfile
import uuid
import re
import math
import xml.etree.ElementTree as ET
from django.shortcuts import get_object_or_404
from django.contrib import messages
from heritage_system.version import VERSION, VERSION_HISTORY

User = get_user_model()


def _b64url_decode(value):
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode('utf-8'))


def _decode_fastapi_token(token):
    try:
        payload_str, signature = token.split('.', 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_str).decode('utf-8'))
    except Exception:
        return None

    if payload.get('exp', 0) < timezone.now().timestamp():
        return None
    return payload


def mobile_kml_entry_view(request):
    token = (request.GET.get('token') or '').strip()
    target_path = request.GET.get('next', '/admin/kml-overlay-check/')
    if not token:
        return HttpResponseForbidden('缺少登录凭证')

    payload = _decode_fastapi_token(token)
    if not payload:
        return HttpResponseForbidden('登录凭证无效或已过期')

    user = User.objects.filter(id=payload.get('user_id'), is_active=True).first()
    if not user:
        return HttpResponseForbidden('用户不存在或已禁用')

    is_admin = user.is_superuser or user.groups.filter(name='管理员').exists() or user.groups.filter(name='超级管理员').exists()
    if not is_admin:
        return HttpResponseForbidden('当前账号无权使用KML叠加检查')

    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    separator = '&' if '?' in target_path else '?'
    return redirect(f"{target_path}{separator}token={quote(token)}")


@staff_member_required
def system_version_api(request):
    """获取系统版本号信息 API"""
    return JsonResponse({
        'status': 'success',
        'version': VERSION,
        'version_history': VERSION_HISTORY,
    })

TOWNSHIP_NORMALIZATION_RULES = [
    ('东巴扎回族乡', '东巴扎回族乡'),
    ('东巴扎乡', '东巴扎回族乡'),
    ('火车站镇', '火车站镇'),
    ('吐峪沟乡', '吐峪沟乡'),
    ('吐峪沟镇', '吐峪沟乡'),
    ('七克台镇', '七克台镇'),
    ('七克台乡', '七克台镇'),
    ('七台镇', '七克台镇'),
    ('连木沁镇', '连木沁镇'),
    ('连木沁乡', '连木沁镇'),
    ('达朗坎乡', '达朗坎乡'),
    ('达浪坎乡', '达朗坎乡'),
    ('鲁克沁镇', '鲁克沁镇'),
    ('辟展镇', '辟展镇'),
    ('辟展乡', '辟展镇'),
    ('鄯善镇', '鄯善镇'),
    ('迪坎镇', '迪坎镇'),
    ('迪坎乡', '迪坎镇'),
]

TOWNSHIP_STANDARD_TO_KEYWORDS = {}
for keyword, standard_name in TOWNSHIP_NORMALIZATION_RULES:
    TOWNSHIP_STANDARD_TO_KEYWORDS.setdefault(standard_name, set()).add(keyword)


@staff_member_required
def heritage_detail_view(request, pk):
    """文物档案详情页 - 只读查看模式"""
    heritage = get_object_or_404(HeritageSite, pk=pk)
    
    # 解析两线坐标数据
    try:
        protection_zone_data = json.loads(heritage.protection_zone) if heritage.protection_zone else []
    except:
        protection_zone_data = []
    
    try:
        control_zone_data = json.loads(heritage.control_zone) if heritage.control_zone else []
    except:
        control_zone_data = []
    
    # 获取相关的巡查记录（字段名是 site，不是 heritage_site）
    inspection_records = InspectionRecord.objects.filter(
        site=heritage
    ).order_by('-inspect_time')[:10]
    
    context = {
        'heritage': heritage,
        'protection_zone_data': protection_zone_data,
        'control_zone_data': control_zone_data,
        'inspection_records': inspection_records,
        'title': f'文物档案详情 - {heritage.name}',
    }
    return render(request, 'admin/heritage_detail.html', context)

@staff_member_required
def admin_index_view(request):
    """自定义管理后台首页 - 显示统计仪表板"""
    current_year = timezone.now().year
    total_sites = HeritageSite.objects.count()
    kanerjing_count = HeritageSite.objects.filter(name__contains='坎儿井').count()
    reviewed_project_count = ProjectAudit.objects.filter(received_date__year=current_year).count()
    checked_coordinate_count = Coordinate.objects.filter(check_status='checked').count()

    pending_projects = ProjectAudit.objects.filter(workflow_status='received').order_by('-received_date')[:12]
    heatmap_points = list(
        HeritageSite.objects.values('name', 'longitude', 'latitude')
    )

    context = {
        'total_sites': total_sites,
        'kanerjing_count': kanerjing_count,
        'reviewed_project_count': reviewed_project_count,
        'checked_coordinate_count': checked_coordinate_count,
        'pending_projects': pending_projects,
        'heatmap_points_json': json.dumps(heatmap_points, ensure_ascii=False),
        'title': '鄯善县文物数字化管理平台',
    }
    return render(request, 'admin/home_dashboard.html', context)


def _render_project_docx(project):
    template_candidates = [
        os.path.join(settings.BASE_DIR, '上行文 {{ file_id }} {{project_name}}.docx'),
        os.path.join(settings.BASE_DIR, '上行文_模板.docx'),
    ]
    template_path = next((path for path in template_candidates if os.path.exists(path)), None)
    if not template_path:
        raise FileNotFoundError(f'模板不存在：{template_candidates[0]}')

    doc = DocxTemplate(template_path)
    issue_date = project.application_date or project.received_date or timezone.now()
    file_id = project.archive_number or f"鄯文旅字〔{issue_date.year}〕{project.id}号"
    coordinates = project.coordinates.all().order_by('tower_no')

    context = {
        'project_name': project.project_name,
        'file_id': file_id,
        'file_no': file_id,
        'issue_date': f'{issue_date.year}年{issue_date.month}月{issue_date.day}日',
        'coordinates': [
            {
                'tower_no': c.tower_no,
                'x': c.cgcs2000_x or '',
                'y': c.cgcs2000_y or '',
                'lon': c.longitude or '',
                'lat': c.latitude or '',
            }
            for c in coordinates
        ],
    }
    doc.render(context)
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output


@staff_member_required
def export_doc_view(request):
    projects = ProjectAudit.objects.order_by('-received_date')[:100]
    if request.method == 'POST':
        selected_ids = request.POST.getlist('project_ids')
        if not selected_ids:
            return render(request, 'admin/export_doc.html', {
                'projects': projects,
                'error': '请至少选择一个项目。'
            })

        selected_projects = ProjectAudit.objects.filter(id__in=selected_ids)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for project in selected_projects:
                doc_stream = _render_project_docx(project)
                filename = f'标准请示公文_{project.project_name}_{project.id}.docx'
                zip_file.writestr(filename, doc_stream.getvalue())

        zip_buffer.seek(0)
        return HttpResponse(
            zip_buffer.getvalue(),
            content_type='application/zip',
            headers={'Content-Disposition': 'attachment; filename="批量公文导出.zip"'}
        )

    return render(request, 'admin/export_doc.html', {'projects': projects})

@staff_member_required  # 确保只有登录后台的人能看
def heritage_map_view(request):
    sites = HeritageSite.objects.all()
    sites_data = []
    for site in sites:
        sites_data.append({
            "name": site.name,
            "lng": float(site.longitude),
            "lat": float(site.latitude),
            "level": site.level  # 使用数据库中的实际等级数据
        })
    
    context = {
        'sites_json': json.dumps(sites_data),
        'title': '鄯善县文物分布一张图'
    }
    return render(request, 'admin/heritage_map.html', context)


def kml_overlay_check_view(request):
    """兼容旧入口：升级后直接复用 KML 文件管理页面"""
    # 兼容跨站 WebView/iframe 场景：会话失效时允许 token 直达鉴权
    if not request.user.is_authenticated:
        token = (request.GET.get('token') or '').strip()
        if token:
            payload = _decode_fastapi_token(token)
            user = User.objects.filter(id=payload.get('user_id'), is_active=True).first() if payload else None
            if user:
                is_admin = user.is_superuser or user.groups.filter(name='管理员').exists() or user.groups.filter(name='超级管理员').exists()
                if is_admin:
                    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return kml_management_view(request)


def _normalize_threshold(raw_value, default=50, min_value=1, max_value=5000):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, value))


def _parse_coordinate_text(coord_text):
    points = []
    if not coord_text:
        return points

    for token in str(coord_text).replace('\n', ' ').replace('\t', ' ').split():
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


def _local_tag_name(tag):
    return tag.split('}', 1)[-1] if '}' in tag else tag


def _find_first_coordinates_text(node):
    for child in node.iter():
        if _local_tag_name(child.tag) == 'coordinates' and child.text:
            return child.text
    return ''


def _extract_features_from_kml_xml(xml_text, source_name):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    features = []
    for placemark in root.iter():
        if _local_tag_name(placemark.tag) != 'Placemark':
            continue

        feature_name = 'KML要素'
        for child in placemark:
            if _local_tag_name(child.tag) == 'name' and child.text and child.text.strip():
                feature_name = child.text.strip()
                break

        for geom in placemark.iter():
            geom_type = _local_tag_name(geom.tag)
            if geom_type not in {'Point', 'LineString', 'Polygon', 'MultiGeometry'}:
                continue

            if geom_type == 'Point':
                points = _parse_coordinate_text(_find_first_coordinates_text(geom))
                if points:
                    features.append({
                        'name': feature_name,
                        'geometry_type': 'Point',
                        'coordinates': points[0],
                        'source': source_name,
                    })

            elif geom_type == 'LineString':
                points = _parse_coordinate_text(_find_first_coordinates_text(geom))
                if points:
                    features.append({
                        'name': feature_name,
                        'geometry_type': 'LineString',
                        'coordinates': points,
                        'source': source_name,
                    })

            elif geom_type == 'Polygon':
                rings = []
                for ring in geom.iter():
                    if _local_tag_name(ring.tag) != 'LinearRing':
                        continue
                    ring_points = _parse_coordinate_text(_find_first_coordinates_text(ring))
                    if ring_points:
                        rings.append(ring_points)
                if rings:
                    features.append({
                        'name': feature_name,
                        'geometry_type': 'Polygon',
                        'coordinates': rings,
                        'source': source_name,
                    })

            elif geom_type == 'MultiGeometry':
                line_geometries = []
                polygon_geometries = []
                for child_geom in geom:
                    child_type = _local_tag_name(child_geom.tag)
                    if child_type == 'Point':
                        points = _parse_coordinate_text(_find_first_coordinates_text(child_geom))
                        if points:
                            features.append({
                                'name': feature_name,
                                'geometry_type': 'Point',
                                'coordinates': points[0],
                                'source': source_name,
                            })
                    elif child_type == 'LineString':
                        points = _parse_coordinate_text(_find_first_coordinates_text(child_geom))
                        if points:
                            line_geometries.append(points)
                    elif child_type == 'Polygon':
                        rings = []
                        for ring in child_geom.iter():
                            if _local_tag_name(ring.tag) != 'LinearRing':
                                continue
                            ring_points = _parse_coordinate_text(_find_first_coordinates_text(ring))
                            if ring_points:
                                rings.append(ring_points)
                        if rings:
                            polygon_geometries.append(rings)

                if line_geometries:
                    features.append({
                        'name': feature_name,
                        'geometry_type': 'MultiLineString',
                        'coordinates': line_geometries,
                        'source': source_name,
                    })
                if polygon_geometries:
                    features.append({
                        'name': feature_name,
                        'geometry_type': 'MultiPolygon',
                        'coordinates': polygon_geometries,
                        'source': source_name,
                    })

    return features


def _extract_features_from_upload(filename, content_bytes):
    lower_name = (filename or '').lower()
    features = []

    if lower_name.endswith('.kmz') or lower_name.endswith('.ovkmz'):
        with zipfile.ZipFile(io.BytesIO(content_bytes), 'r') as zf:
            for member in zf.namelist():
                if not member.lower().endswith('.kml'):
                    continue
                text = zf.read(member).decode('utf-8', errors='ignore')
                features.extend(_extract_features_from_kml_xml(text, f"{filename}:{member}"))
    else:
        text = content_bytes.decode('utf-8', errors='ignore')
        features.extend(_extract_features_from_kml_xml(text, filename))

    return features


def _haversine_m(lat1, lon1, lat2, lon2):
    radius = 6371000
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distance_point_to_segment_m(lat, lon, lat1, lon1, lat2, lon2):
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * math.cos(math.radians((lat1 + lat2) / 2))

    px = lon * meters_per_deg_lon
    py = lat * meters_per_deg_lat
    x1 = lon1 * meters_per_deg_lon
    y1 = lat1 * meters_per_deg_lat
    x2 = lon2 * meters_per_deg_lon
    y2 = lat2 * meters_per_deg_lat

    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _distance_to_linestring_m(site_lon, site_lat, line_coords):
    if not line_coords:
        return float('inf')
    if len(line_coords) == 1:
        lon, lat = line_coords[0]
        return _haversine_m(site_lat, site_lon, lat, lon)

    min_distance = float('inf')
    for idx in range(len(line_coords) - 1):
        lon1, lat1 = line_coords[idx]
        lon2, lat2 = line_coords[idx + 1]
        distance = _distance_point_to_segment_m(site_lat, site_lon, lat1, lon1, lat2, lon2)
        min_distance = min(min_distance, distance)
    return min_distance


def _is_point_in_ring(lon, lat, ring):
    if not ring or len(ring) < 3:
        return False

    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _is_point_in_polygon(lon, lat, polygon_rings):
    if not polygon_rings:
        return False
    if not _is_point_in_ring(lon, lat, polygon_rings[0]):
        return False
    for hole_ring in polygon_rings[1:]:
        if _is_point_in_ring(lon, lat, hole_ring):
            return False
    return True


def _analyze_conflicts(features, threshold_m):
    site_points = list(
        HeritageSite.objects.exclude(longitude__isnull=True).exclude(latitude__isnull=True).values(
            'id', 'name', 'level', 'longitude', 'latitude'
        )
    )
    threshold = float(threshold_m)
    conflicts = []

    for feature in features:
        feature_type = feature.get('geometry_type')
        feature_name = feature.get('name') or 'KML要素'
        feature_source = feature.get('source') or ''
        coords = feature.get('coordinates')

        for site in site_points:
            site_lon = float(site['longitude'])
            site_lat = float(site['latitude'])

            matched = False
            relation = ''
            distance_m = None

            if feature_type == 'Point' and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lon, lat = float(coords[0]), float(coords[1])
                distance_m = _haversine_m(site_lat, site_lon, lat, lon)
                matched = distance_m <= threshold
                relation = '点距离'
            elif feature_type == 'LineString':
                distance_m = _distance_to_linestring_m(site_lon, site_lat, coords or [])
                matched = distance_m <= threshold
                relation = '线最短距离'
            elif feature_type == 'MultiLineString':
                min_distance = float('inf')
                for line_coords in (coords or []):
                    min_distance = min(min_distance, _distance_to_linestring_m(site_lon, site_lat, line_coords))
                distance_m = min_distance
                matched = distance_m <= threshold
                relation = '线最短距离'
            elif feature_type == 'Polygon':
                matched = _is_point_in_polygon(site_lon, site_lat, coords or [])
                relation = '面内包含'
            elif feature_type == 'MultiPolygon':
                matched = any(_is_point_in_polygon(site_lon, site_lat, polygon) for polygon in (coords or []))
                relation = '面内包含'

            if matched:
                conflicts.append({
                    'feature_name': feature_name,
                    'feature_type': feature_type,
                    'feature_source': feature_source,
                    'site_id': site['id'],
                    'site_name': site['name'],
                    'site_level': site['level'],
                    'relation': relation,
                    'distance_m': None if distance_m is None or not math.isfinite(distance_m) else round(distance_m, 2),
                })

    return conflicts


def _build_conflict_report_csv(conflicts, threshold_m):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['阈值(米)', threshold_m])
    writer.writerow([])
    writer.writerow(['文件来源', '要素名称', '要素类型', '文物ID', '文物名称', '文物级别', '冲突关系', '距离(米)'])

    if conflicts:
        for row in conflicts:
            writer.writerow([
                row.get('feature_source', ''),
                row.get('feature_name', ''),
                row.get('feature_type', ''),
                row.get('site_id', ''),
                row.get('site_name', ''),
                row.get('site_level', ''),
                row.get('relation', ''),
                '' if row.get('distance_m') is None else row.get('distance_m'),
            ])
    else:
        writer.writerow(['-', '-', '-', '-', '无冲突', '-', '-', '-'])

    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="kml_conflict_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    return response


def _is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.groups.filter(name='管理员').exists()
        or user.groups.filter(name='超级管理员').exists()
    )


@staff_member_required
def kml_management_view(request):
    if not _is_admin_user(request.user):
        return HttpResponseForbidden('需要管理员权限')

    if request.method == 'POST':
        row_delete_id = request.POST.get('row_delete_id')
        if row_delete_id:
            record = KmlUploadRecord.objects.filter(id=row_delete_id).first()
            if not record:
                messages.error(request, '要删除的记录不存在。')
            else:
                if record.source_file:
                    record.source_file.delete(save=False)
                record.delete()
                messages.success(request, 'KML 文件记录已删除。')
            return redirect('kml_overlay_check')

        row_rename_id = request.POST.get('row_rename_id')
        if row_rename_id:
            record = KmlUploadRecord.objects.filter(id=row_rename_id).first()
            if not record:
                messages.error(request, '要重命名的记录不存在。')
                return redirect('kml_overlay_check')

            new_title = (request.POST.get(f'rename_title_{row_rename_id}') or '').strip()
            if not new_title:
                messages.error(request, '新名称不能为空。')
                return redirect('kml_overlay_check')

            if len(new_title) > 255:
                messages.error(request, '新名称长度不能超过255个字符。')
                return redirect('kml_overlay_check')

            record.title = new_title
            record.save(update_fields=['title', 'updated_at'])
            messages.success(request, f'已重命名为：{new_title}')
            return redirect('kml_overlay_check')

        action = request.POST.get('action', 'upload')
        threshold = _normalize_threshold(request.POST.get('threshold_m', 50))

        if action == 'upload':
            upload_files = request.FILES.getlist('kml_files')
            if not upload_files:
                messages.error(request, '请至少选择一个KML/KMZ/OVKML/OVKMZ文件。')
                return redirect('kml_overlay_check')

            created_count = 0
            total_conflicts = 0
            for upload in upload_files:
                name = upload.name or '未命名文件'
                lower_name = name.lower()
                if not (lower_name.endswith('.kml') or lower_name.endswith('.ovkml') or lower_name.endswith('.kmz') or lower_name.endswith('.ovkmz')):
                    messages.warning(request, f'已跳过不支持的文件：{name}')
                    continue

                content = upload.read()
                upload.seek(0)
                try:
                    features = _extract_features_from_upload(name, content)
                except Exception as exc:
                    messages.error(request, f'{name} 解析失败：{exc}')
                    continue

                conflicts = _analyze_conflicts(features, threshold)
                total_conflicts += len(conflicts)

                report_payload = {
                    'threshold_m': threshold,
                    'feature_count': len(features),
                    'conflict_count': len(conflicts),
                    'generated_at': timezone.now().isoformat(),
                    'conflicts': conflicts,
                }
                KmlUploadRecord.objects.create(
                    title=name,
                    source_file=upload,
                    uploaded_by=request.user,
                    threshold_m=threshold,
                    feature_count=len(features),
                    conflict_count=len(conflicts),
                    report_json=json.dumps(report_payload, ensure_ascii=False),
                )
                created_count += 1

            if created_count:
                messages.success(request, f'已上传并分析 {created_count} 个文件，共发现 {total_conflicts} 处冲突。')
            return redirect('kml_overlay_check')

        if action == 'analyze_selected':
            selected_ids = request.POST.getlist('selected_ids')
            if not selected_ids:
                messages.error(request, '请先选择要批量查询的文件。')
                return redirect('kml_overlay_check')

            selected_records = list(KmlUploadRecord.objects.filter(id__in=selected_ids))
            if not selected_records:
                messages.error(request, '未找到选中的文件记录。')
                return redirect('kml_overlay_check')

            combined_conflicts = []
            for record in selected_records:
                try:
                    with record.source_file.open('rb') as source:
                        content = source.read()
                    features = _extract_features_from_upload(record.title, content)
                    conflicts = _analyze_conflicts(features, threshold)
                except Exception as exc:
                    messages.warning(request, f'{record.title} 重新分析失败：{exc}')
                    continue

                record.threshold_m = threshold
                record.feature_count = len(features)
                record.conflict_count = len(conflicts)
                record.report_json = json.dumps({
                    'threshold_m': threshold,
                    'feature_count': len(features),
                    'conflict_count': len(conflicts),
                    'generated_at': timezone.now().isoformat(),
                    'conflicts': conflicts,
                }, ensure_ascii=False)
                record.save(update_fields=['threshold_m', 'feature_count', 'conflict_count', 'report_json', 'updated_at'])

                combined_conflicts.extend(conflicts)

            return _build_conflict_report_csv(combined_conflicts, threshold)

    records = KmlUploadRecord.objects.select_related('uploaded_by').order_by('-created_at')[:200]
    sites_data = list(
        HeritageSite.objects.exclude(longitude__isnull=True).exclude(latitude__isnull=True).values(
            'id', 'name', 'level', 'longitude', 'latitude'
        )
    )
    context = {
        'title': 'KML文件管理与批量冲突检查',
        'records': records,
        'default_threshold': 50,
        'sites_json': json.dumps(sites_data, ensure_ascii=False),
    }
    return render(request, 'admin/kml_management.html', context)


@staff_member_required
@staff_member_required
def ovkml_converter_view(request):
    """OVKML/KML/KMZ/OVKMZ 网页转换工具：提取坐标并导出可导入 ProjectAudit 的 CSV。"""
    context = {
        'title': 'KML/KMZ转换导入',
        'input_crs': 'wgs84',
        'output_crs': 'cgcs2000',
        'deduplicate': True,
    }

    if request.method == 'POST':
        upload_file = request.FILES.get('ovkml_file')
        input_crs = request.POST.get('input_crs', 'wgs84')
        output_crs = request.POST.get('output_crs', 'cgcs2000')
        action = request.POST.get('action', 'convert')
        deduplicate = request.POST.get('deduplicate') == 'on'

        context['input_crs'] = input_crs
        context['output_crs'] = output_crs
        context['deduplicate'] = deduplicate

        if not upload_file:
            context['error'] = '请先选择 KML/KMZ/OVKML/OVKMZ 文件。'
            return render(request, 'admin/ovkml_converter.html', context)

        filename = (upload_file.name or '').lower()
        # 支持 .kml, .ovkml, .kmz, .ovkmz
        if not (filename.endswith('.kml') or filename.endswith('.ovkml') or 
                filename.endswith('.kmz') or filename.endswith('.ovkmz')):
            context['error'] = '文件格式不正确，请上传 .kml .kmz .ovkml .ovkmz 文件。'
            return render(request, 'admin/ovkml_converter.html', context)

        try:
            from core.ovkml_converter import parse_kml_or_kmz
            records, file_format = parse_kml_or_kmz(upload_file.read(), input_crs=input_crs, output_crs=output_crs)
        except Exception as exc:
            context['error'] = f'解析失败：{exc}'
            return render(request, 'admin/ovkml_converter.html', context)

        if not records:
            context['error'] = '未提取到 Placemark，请检查文件内容或嵌套结构。'
            return render(request, 'admin/ovkml_converter.html', context)

        project_csv, detail_csv = build_csv_outputs(records)

        export_dir = os.path.join(settings.MEDIA_ROOT, 'ovkml_exports')
        os.makedirs(export_dir, exist_ok=True)
        export_id = uuid.uuid4().hex

        project_filename = f'{export_id}_projectaudit.csv'
        detail_filename = f'{export_id}_detail.csv'
        project_path = os.path.join(export_dir, project_filename)
        detail_path = os.path.join(export_dir, detail_filename)

        with open(project_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(project_csv)
        with open(detail_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(detail_csv)

        preview_rows = []
        for item in records[:100]:
            preview_rows.append({
                'project_name': item.project_name,
                'geometry_type': item.geometry_type,
                'vertex_count': item.vertex_count,
                'project_lon': '' if item.target_lon is None else f'{item.target_lon:.10f}',
                'project_lat': '' if item.target_lat is None else f'{item.target_lat:.10f}',
                'cgcs2000_x': '' if item.cgcs2000_x is None else f'{item.cgcs2000_x:.3f}',
                'cgcs2000_y': '' if item.cgcs2000_y is None else f'{item.cgcs2000_y:.3f}',
                'source_folder': item.source_folder,
            })

        context.update({
            'success': True,
            'total_count': len(records),
            'preview_rows': preview_rows,
            'project_csv_url': f"{settings.MEDIA_URL}ovkml_exports/{project_filename}",
            'detail_csv_url': f"{settings.MEDIA_URL}ovkml_exports/{detail_filename}",
            'preview_truncated': len(records) > 100,
            'file_format': file_format,
        })

        if action == 'import':
            existing_keys = set()
            if deduplicate:
                for item in ProjectAudit.objects.only('project_name', 'project_lon', 'project_lat'):
                    lon_key = '' if item.project_lon is None else f"{item.project_lon:.6f}"
                    lat_key = '' if item.project_lat is None else f"{item.project_lat:.6f}"
                    existing_keys.add((item.project_name.strip(), lon_key, lat_key))

            batch_seen = set()
            to_create = []
            skipped_count = 0

            for item in records:
                lon_key = '' if item.target_lon is None else f"{item.target_lon:.6f}"
                lat_key = '' if item.target_lat is None else f"{item.target_lat:.6f}"
                row_key = (item.project_name.strip(), lon_key, lat_key)

                if deduplicate and (row_key in existing_keys or row_key in batch_seen):
                    skipped_count += 1
                    continue

                batch_seen.add(row_key)
                to_create.append(
                    ProjectAudit(
                        project_name=item.project_name,
                        project_unit='',
                        construction_content='',
                        project_scale='',
                        project_coordinates=item.project_coordinates,
                        project_lon=item.target_lon,
                        project_lat=item.target_lat,
                        workflow_status='received',
                        remarks=f"来源文件夹:{item.source_folder or '-'}; 几何:{item.geometry_type}; 顶点:{item.vertex_count}; 导入来源:KML/KMZ转换工具",
                        received_date=timezone.now(),
                    )
                )

            if to_create:
                ProjectAudit.objects.bulk_create(to_create)

            context['import_done'] = True
            context['import_count'] = len(to_create)
            context['import_skipped_count'] = skipped_count

    return render(request, 'admin/ovkml_converter.html', context)


@staff_member_required
def heritage_dashboard_view(request):
    """文物分类统计面板"""
    total = HeritageSite.objects.count()
    township_counter = {}
    for address in HeritageSite.objects.values_list('address', flat=True):
        township_name = _extract_township_name(address)
        if township_name:
            township_counter[township_name] = township_counter.get(township_name, 0) + 1

    township_options = [
        {
            'value': item[0],
            'label': _to_township_full_name(item[0]),
        }
        for item in sorted(township_counter.items(), key=lambda x: x[1], reverse=True)
    ]

    context = {
        'total_sites': total,
        'title': '文物分类统计面板',
        'category_choices_json': json.dumps(list(HeritageSite.CATEGORY_CHOICES), ensure_ascii=False),
        'level_choices_json': json.dumps(list(HeritageSite.LEVEL_CHOICES), ensure_ascii=False),
        'township_options_json': json.dumps(township_options, ensure_ascii=False),
    }
    return render(request, 'admin/heritage_dashboard.html', context)


def _extract_township_name(address):
    if not address:
        return ''

    text = str(address).strip()
    for keyword, standard_name in TOWNSHIP_NORMALIZATION_RULES:
        if keyword in text:
            return standard_name

    match = re.search(r'鄯善县(?:吐鲁番市鄯善县)*(?:东北)?([\u4e00-\u9fa5]{1,12}?(?:回族乡|乡|镇|街道))', text)
    if match:
        return match.group(1)

    return ''


def _to_township_full_name(township_name):
    if not township_name:
        return ''
    if township_name.startswith('鄯善县'):
        return township_name
    return f'鄯善县{township_name}'


@staff_member_required
def heritage_classification_stats_api(request):
    """文物分类统计面板实时数据 API（支持高级筛选）"""
    category = request.GET.get('category', '').strip()
    level = request.GET.get('level', '').strip()
    township = request.GET.get('township', '').strip()
    address_keyword = request.GET.get('address_keyword', '').strip()
    group_by = request.GET.get('group_by', 'category').strip()

    queryset = HeritageSite.objects.all()
    if category:
        queryset = queryset.filter(category=category)
    if level:
        queryset = queryset.filter(level=level)
    if township:
        township_keywords = TOWNSHIP_STANDARD_TO_KEYWORDS.get(township, {township})
        township_query = Q()
        for keyword in township_keywords:
            township_query |= Q(address__icontains=keyword)
        queryset = queryset.filter(township_query)
    if address_keyword:
        queryset = queryset.filter(address__icontains=address_keyword)

    labels = []
    data = []

    if group_by == 'level':
        stats = queryset.values('level').annotate(count=Count('id')).order_by('-count')
        level_name_map = dict(HeritageSite.LEVEL_CHOICES)
        labels = [level_name_map.get(item['level'], item['level']) for item in stats]
        data = [item['count'] for item in stats]
    elif group_by == 'township':
        township_counter = {}
        for item in queryset.values('address'):
            township_name = _extract_township_name(item.get('address'))
            key = township_name or '未标注乡镇'
            township_counter[key] = township_counter.get(key, 0) + 1
        sorted_items = sorted(township_counter.items(), key=lambda x: x[1], reverse=True)
        labels = [
            '未标注乡镇' if item[0] == '未标注乡镇' else _to_township_full_name(item[0])
            for item in sorted_items
        ]
        data = [item[1] for item in sorted_items]
    else:
        stats = queryset.values('category').annotate(count=Count('id')).order_by('-count')
        category_name_map = dict(HeritageSite.CATEGORY_CHOICES)
        labels = [category_name_map.get(item['category'], item['category']) for item in stats]
        data = [item['count'] for item in stats]

    return JsonResponse({
        'labels': labels,
        'data': data,
        'total': queryset.count(),
    })


@staff_member_required
def heritage_stats_api(request):
    """统计数据 API 端点"""
    total = HeritageSite.objects.count()
    national = HeritageSite.objects.filter(level='GB').count()
    regional = HeritageSite.objects.filter(level='SB').count()
    county = HeritageSite.objects.filter(level='XB').count()
    
    return JsonResponse({
        'total': total,
        'national': national,
        'regional': regional,
        'county': county,
    })

@staff_member_required
def heritage_stats_by_category_api(request):
    """按类别统计的 API 端点"""
    category_stats = HeritageSite.objects.values('category').annotate(count=Count('id'))
    
    labels = []
    data = []
    
    for stat in category_stats:
        category_code = stat['category']
        # 获取中文标签
        category_name = dict(HeritageSite.CATEGORY_CHOICES).get(category_code, category_code)
        labels.append(category_name)
        data.append(stat['count'])
    
    return JsonResponse({
        'labels': labels,
        'data': data,
    })

@staff_member_required
def kanerjing_list_view(request):
    """坎儿井专项管理页面 - 基于名称包含'坎儿井'进行筛选"""
    kanerjing_sites = HeritageSite.objects.filter(name__contains='坎儿井')
    total_kanerjing = kanerjing_sites.count()
    
    # 按等级统计
    kanerjing_by_level = kanerjing_sites.values('level').annotate(count=Count('id'))
    level_stats = {}
    for stat in kanerjing_by_level:
        level_name = dict(HeritageSite.LEVEL_CHOICES).get(stat['level'], stat['level'])
        level_stats[level_name] = stat['count']
    
    context = {
        'kanerjing_sites': kanerjing_sites,
        'total_kanerjing': total_kanerjing,
        'level_stats': level_stats,
        'title': '坎儿井专项管理'
    }
    return render(request, 'admin/kanerjing_list.html', context)

@staff_member_required
def kanerjing_stats_api(request):
    """坎儿井统计 API - 基于名称包含'坎儿井'进行筛选"""
    kanerjing_sites = HeritageSite.objects.filter(name__contains='坎儿井')
    total = kanerjing_sites.count()
    
    # 按等级统计
    level_breakdown = {}
    for level_code, level_name in HeritageSite.LEVEL_CHOICES:
        count = kanerjing_sites.filter(level=level_code).count()
        level_breakdown[level_name] = count
    
    # 按地址统计
    address_distribution = kanerjing_sites.values('address').annotate(count=Count('id')).order_by('-count')[:10]
    
    return JsonResponse({
        'total': total,
        'by_level': level_breakdown,
        'top_addresses': list(address_distribution),
    })

@staff_member_required
def kanerjing_import_check_view(request):
    """导入后检查坎儿井数据"""
    kanerjing_count = HeritageSite.objects.filter(name__contains='坎儿井').count()
    total_count = HeritageSite.objects.count()
    
    context = {
        'kanerjing_count': kanerjing_count,
        'total_count': total_count,
        'kanerjing_percentage': round((kanerjing_count / total_count * 100), 1) if total_count > 0 else 0,
        'title': '坎儿井数据检查报告'
    }
    return render(request, 'admin/kanerjing_import_check.html', context)


# 自定义密码修改完成视图
from django.contrib.auth.views import PasswordChangeDoneView
from .signals import mark_password_changed


class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    """自定义密码修改完成视图 - 标记用户已修改密码"""
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 标记用户已修改密码
        mark_password_changed(self.request.user)
        
        # 添加自定义信息
        from django.contrib import messages
        messages.success(
            self.request,
            '✓ 密码修改成功！您的账户更安全了。'
        )
        
        return context


@staff_member_required
def inspection_mobile_add_view(request):
    """
    手机端优化的巡查记录添加页面
    提供友好的手机界面，用于现场快速添加巡查记录
    
    权限逻辑：
    - 看护员用户组：inspector字段自动锁定为当前登录用户（不可修改）
    - 其他用户（管理员等）：inspector字段可自由选择
    """
    import json
    from django.contrib.auth.models import Group, User
    from datetime import datetime
    
    # 检查用户是否属于"文物看护员"用户组
    is_inspector = request.user.groups.filter(name='文物看护员').exists()
    
    if request.method == 'POST':
        # 处理AJAX POST请求
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
                site_id = data.get('site')
                inspect_time = data.get('inspect_time')
                is_normal_value = data.get('is_normal')
                issue_details = data.get('issue_details', '')
                inspector_id = data.get('inspector')
                photo_file = None
            else:
                data = request.POST
                site_id = data.get('site')
                inspect_time = data.get('inspect_time')
                is_normal_value = data.get('is_normal')
                issue_details = data.get('issue_details', '')
                inspector_id = data.get('inspector')
                photo_file = request.FILES.get('photo')

            # 验证必填字段
            is_normal = str(is_normal_value).lower() == 'true'
            
            if not site_id or not inspect_time:
                return JsonResponse({
                    'success': False,
                    'message': '请填写必填字段'
                }, status=400)

            if not photo_file:
                return JsonResponse({
                    'success': False,
                    'message': '请上传现场照片（带经纬度时间水印）'
                }, status=400)
            
            # 获取文物点
            try:
                site = HeritageSite.objects.get(id=site_id)
            except HeritageSite.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': '文物点不存在'
                }, status=404)
            
            # 根据用户组决定 inspector 赋值方式
            if is_inspector:
                # 看护员用户：强制使用当前登录用户，忽略客户端提交的值
                inspector = request.user
            else:
                # 其他用户（管理员等）：允许指定巡查员
                if not inspector_id:
                    inspector = request.user  # 如果未指定，使用当前用户
                else:
                    try:
                        inspector = User.objects.get(id=inspector_id)
                    except User.DoesNotExist:
                        return JsonResponse({
                            'success': False,
                            'message': '指定的巡查员不存在'
                        }, status=404)
            
            # 创建巡查记录
            record = InspectionRecord(
                site=site,
                inspector=inspector,
                inspect_time=datetime.fromisoformat(inspect_time),
                is_normal=is_normal,
                issue_details=issue_details,
                photo=photo_file
            )
            record.save()
            
            return JsonResponse({
                'success': True,
                'message': '巡查记录已保存',
                'record_id': record.id,
                'inspector_name': f"{inspector.first_name or inspector.username}"  # 返回记录者信息确认
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '请求格式错误'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'保存失败: {str(e)}'
            }, status=500)
    
    # GET 请求：返回手机优化的表单页面
    sites_data = list(
        HeritageSite.objects.all().values(
            'id', 'name', 'category', 'level', 'longitude', 'latitude'
        )
    )
    
    context = {
        'sites_json': json.dumps(sites_data),  # JSON格式供前端搜索筛选
        'sites': sites_data,  # 也提供列表格式
        'current_user': f"{request.user.first_name or request.user.username}",
        'is_inspector': is_inspector,  # 传递权限标志
    }
    
    # 如果不是看护员，添加可选巡查员列表
    if not is_inspector:
        inspectors = User.objects.filter(groups__name='文物看护员').values('id', 'first_name', 'username')
        context['inspectors'] = inspectors
    
    return render(request, 'admin/inspection_mobile.html', context)


@staff_member_required
def inspection_mobile_list_view(request):
    """
    手机端巡查记录列表 - 卡片式展示
    显示当前用户的所有巡查记录
    """
    # 获取当前用户的巡查记录 - 同时加载相关的site和inspector对象以提高效率
    records = InspectionRecord.objects.filter(
        inspector=request.user
    ).select_related('site', 'inspector').order_by('-inspect_time')
    
    # 分页
    from django.core.paginator import Paginator
    paginator = Paginator(records, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'records': page_obj.object_list,
        'total_count': paginator.count,
    }
    return render(request, 'admin/inspection_mobile_list.html', context)


def app_showcase_view(request):
    """鄯善文保 App 展示与下载页（公开访问）"""
    context = {
        'download_url': 'https://share.fnnas.net/s/49a5a7b485784cf4a1',
        'qr_code_url': 'https://api.qrserver.com/v1/create-qr-code/?size=280x280&data=https%3A%2F%2Fshare.fnnas.net%2Fs%2F49a5a7b485784cf4a1',
        'features': [
            '文物点巡查上报：支持现场拍照、位置记录与问题描述，提升巡查效率。',
            '巡查记录管理：随时查看历史巡查内容，支持按时间快速追溯。',
            '关联中心协同：重点任务与相关文物信息关联展示，便于统一处置。',
            '个人账户中心：看护员可管理个人信息与使用入口，操作清晰。',
        ],
        'screenshots': [
            {'name': '登录页面', 'file': 'app_showcase/登录页面.jpg'},
            {'name': '工作台', 'file': 'app_showcase/工作台.jpg'},
            {'name': '巡查上报', 'file': 'app_showcase/巡查上报.jpg'},
            {'name': '巡查记录', 'file': 'app_showcase/巡查记录.jpg'},
            {'name': '关联中心', 'file': 'app_showcase/关联中心.jpg'},
            {'name': '我的账户', 'file': 'app_showcase/我的账户.jpg'},
        ],
    }
    return render(request, 'public/app_showcase.html', context)

