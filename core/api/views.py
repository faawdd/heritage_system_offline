import json
import io
import os
import uuid
import zipfile
import csv
import re
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core import views as legacy_views
from core.models import HeritageSite, InspectionRecord, KmlUploadRecord, LandUseProjectApproval, ProjectAudit
from core.permission_decorators import can_modify_core_data
from core.permissions.api_permissions import IsManagementAdmin
from core.services.heritage_service import (
    get_heritage_detail_payload,
    get_heritage_map_points,
    get_heritage_stats_meta,
)
from core.services.system_service import get_system_version_payload
from core.ovkml_converter import build_csv_outputs, parse_kml_or_kmz


class HealthAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({'status': 'ok'})


class SystemVersionAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        payload = get_system_version_payload()
        return Response({'success': True, 'data': payload})


class DashboardOverviewAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        today = timezone.localdate()
        today_inspections = InspectionRecord.objects.filter(inspect_time__date=today).count()
        abnormal_inspections = InspectionRecord.objects.filter(is_normal=False).count()
        heritage_total = HeritageSite.objects.count()

        # 近7天巡查趋势（含异常数量）。
        start_date = today - timedelta(days=6)
        total_by_day = {
            item['inspect_time__date']: item['count']
            for item in InspectionRecord.objects.filter(inspect_time__date__range=[start_date, today])
            .values('inspect_time__date')
            .annotate(count=Count('id'))
        }
        abnormal_by_day = {
            item['inspect_time__date']: item['count']
            for item in InspectionRecord.objects.filter(is_normal=False, inspect_time__date__range=[start_date, today])
            .values('inspect_time__date')
            .annotate(count=Count('id'))
        }

        inspection_trend_7d = []
        for i in range(7):
            current = start_date + timedelta(days=i)
            inspection_trend_7d.append(
                {
                    'date': current.isoformat(),
                    'label': current.strftime('%m-%d'),
                    'total_count': total_by_day.get(current, 0),
                    'abnormal_count': abnormal_by_day.get(current, 0),
                }
            )

        # 2.0流程：处于审批/流转中的项目视为“待审批项目”。
        pending_project_count = LandUseProjectApproval.objects.filter(
            status__in=[
                LandUseProjectApproval.STATUS_CITY_REVIEWING,
                LandUseProjectApproval.STATUS_ARCHAEOLOGY,
                LandUseProjectApproval.STATUS_REPLY_RECEIVED,
            ]
        ).count()

        # 兼容历史数据：若新流程尚未启用，则回退到旧ProjectAudit待审统计。
        if pending_project_count == 0:
            pending_project_count = ProjectAudit.objects.filter(status='Pending').count()

        # 项目审批漏斗（按新流程状态）。
        project_status_count_map = {
            item['status']: item['count']
            for item in LandUseProjectApproval.objects.values('status').annotate(count=Count('id'))
        }
        project_funnel = [
            {
                'status': status,
                'label': label,
                'count': project_status_count_map.get(status, 0),
            }
            for status, label in LandUseProjectApproval.STATUS_CHOICES
        ]

        # 兼容老数据：新流程为空时用旧项目状态提供最小漏斗。
        if sum(item['count'] for item in project_funnel) == 0:
            legacy_status_map = {
                item['status']: item['count']
                for item in ProjectAudit.objects.values('status').annotate(count=Count('id'))
            }
            project_funnel = [
                {'status': 'Pending', 'label': '待审', 'count': legacy_status_map.get('Pending', 0)},
                {'status': 'Pass', 'label': '通过', 'count': legacy_status_map.get('Pass', 0)},
                {'status': 'Reject', 'label': '驳回', 'count': legacy_status_map.get('Reject', 0)},
            ]

        abnormal_inspection_points = []
        abnormal_qs = (
            InspectionRecord.objects.select_related('site')
            .filter(is_normal=False, longitude__isnull=False, latitude__isnull=False)
            .order_by('-inspect_time')[:600]
        )
        for item in abnormal_qs:
            try:
                lon = float(item.longitude)
                lat = float(item.latitude)
            except (TypeError, ValueError):
                continue
            abnormal_inspection_points.append(
                {
                    'id': item.id,
                    'site_id': item.site_id,
                    'site_name': item.site.name if item.site else '-',
                    'longitude': lon,
                    'latitude': lat,
                    'inspect_time': item.inspect_time.strftime('%Y-%m-%d %H:%M'),
                    'issue_details': item.issue_details or '',
                }
            )

        return Response(
            {
                'success': True,
                'data': {
                    'pending_project_count': pending_project_count,
                    'today_inspection_count': today_inspections,
                    'heritage_total_count': heritage_total,
                    'risk_warning_count': abnormal_inspections,
                    'inspection_trend_7d': inspection_trend_7d,
                    'project_funnel': project_funnel,
                    'abnormal_inspection_points': abnormal_inspection_points,
                },
            }
        )


class HeritageMapPointsAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = get_heritage_map_points()
        return Response({'success': True, 'rows': rows})


class HeritageStatsMetaAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        data = get_heritage_stats_meta()
        return Response({'success': True, 'data': data})


class HeritageDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, site_id):
        payload = get_heritage_detail_payload(site_id)
        if not payload:
            return Response({'success': False, 'message': '文物不存在'}, status=404)
        return Response({'success': True, 'data': payload})


class ImmovableHeritageListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        category = (request.GET.get('category') or '').strip()
        level = (request.GET.get('level') or '').strip()
        page = max(int(request.GET.get('page', 1) or 1), 1)
        page_size = min(max(int(request.GET.get('page_size', 20) or 20), 1), 200)

        queryset = HeritageSite.objects.all().order_by('id')

        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(sip_code__icontains=keyword)
                | Q(address__icontains=keyword)
                | Q(manager__icontains=keyword)
                | Q(description__icontains=keyword)
            )

        if category:
            queryset = queryset.filter(category=category)
        if level:
            queryset = queryset.filter(level=level)

        total = queryset.count()
        offset = (page - 1) * page_size
        rows = []
        for item in queryset[offset: offset + page_size]:
            rows.append(
                {
                    'id': item.id,
                    'name': item.name,
                    'preview_url': f'/mobile/collect/{item.id}/preview/?mode=view',
                    'sip_code': item.sip_code,
                    'category': item.category,
                    'category_label': item.get_category_display(),
                    'level': item.level,
                    'level_label': item.get_level_display(),
                    'address': item.address,
                    'longitude': item.longitude,
                    'latitude': item.latitude,
                    'manager': item.manager,
                    'description': item.description,
                    'protection_zone': item.protection_zone,
                    'control_zone': item.control_zone,
                }
            )

        return Response(
            {
                'success': True,
                'rows': rows,
                'meta': {
                    'category_choices': [{'value': code, 'label': label} for code, label in HeritageSite.CATEGORY_CHOICES],
                    'level_choices': [{'value': code, 'label': label} for code, label in HeritageSite.LEVEL_CHOICES],
                },
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                },
            }
        )


class ImmovableHeritageDetailAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def patch(self, request, site_id):
        if not can_modify_core_data(request.user):
            return Response({'success': False, 'message': '当前角色仅可查看，禁止修改'}, status=403)

        site = HeritageSite.objects.filter(id=site_id).first()
        if not site:
            return Response({'success': False, 'message': '文物档案不存在'}, status=404)

        text_fields = ['name', 'sip_code', 'address', 'manager', 'description', 'protection_zone', 'control_zone']
        for field in text_fields:
            if field in request.data:
                setattr(site, field, (request.data.get(field) or '').strip())

        if 'category' in request.data:
            category = (request.data.get('category') or '').strip()
            category_values = {value for value, _label in HeritageSite.CATEGORY_CHOICES}
            if category not in category_values:
                return Response({'success': False, 'message': '文物类别非法'}, status=400)
            site.category = category

        if 'level' in request.data:
            level = (request.data.get('level') or '').strip()
            level_values = {value for value, _label in HeritageSite.LEVEL_CHOICES}
            if level not in level_values:
                return Response({'success': False, 'message': '保护级别非法'}, status=400)
            site.level = level

        if 'longitude' in request.data:
            try:
                site.longitude = float(request.data.get('longitude'))
            except (TypeError, ValueError):
                return Response({'success': False, 'message': '经度格式非法'}, status=400)

        if 'latitude' in request.data:
            try:
                site.latitude = float(request.data.get('latitude'))
            except (TypeError, ValueError):
                return Response({'success': False, 'message': '纬度格式非法'}, status=400)

        try:
            site.save()
        except Exception as exc:
            return Response({'success': False, 'message': f'保存失败: {exc}'}, status=400)

        return Response({'success': True, 'message': '文物档案已更新'})


class ImmovableHeritageImportAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not can_modify_core_data(request.user):
            return Response({'success': False, 'message': '当前角色仅可查看，禁止修改'}, status=403)

        upload = request.FILES.get('file')
        if not upload:
            return Response({'success': False, 'message': '请上传CSV文件'}, status=400)

        if not upload.name.lower().endswith('.csv'):
            return Response({'success': False, 'message': '仅支持CSV文件导入'}, status=400)

        try:
            content = upload.read()
            text = content.decode('utf-8-sig')
        except Exception:
            try:
                text = content.decode('gb18030')
            except Exception as exc:
                return Response({'success': False, 'message': f'文件解析失败: {exc}'}, status=400)

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return Response({'success': False, 'message': 'CSV表头为空'}, status=400)

        category_map = {label: value for value, label in HeritageSite.CATEGORY_CHOICES}
        level_map = {label: value for value, label in HeritageSite.LEVEL_CHOICES}

        updated_count = 0
        created_count = 0
        skipped_rows = []

        for index, row in enumerate(reader, start=2):
            sip_code = (row.get('四普编号') or row.get('sip_code') or '').strip()
            if not sip_code:
                skipped_rows.append({'line': index, 'reason': '缺少四普编号'})
                continue

            category_raw = (row.get('文物类别') or row.get('category') or '').strip()
            level_raw = (row.get('保护级别') or row.get('level') or '').strip()
            category = category_map.get(category_raw, category_raw)
            level = level_map.get(level_raw, level_raw)

            valid_categories = {value for value, _label in HeritageSite.CATEGORY_CHOICES}
            valid_levels = {value for value, _label in HeritageSite.LEVEL_CHOICES}
            if category not in valid_categories:
                skipped_rows.append({'line': index, 'reason': f'文物类别非法: {category_raw}'})
                continue
            if level not in valid_levels:
                skipped_rows.append({'line': index, 'reason': f'保护级别非法: {level_raw}'})
                continue

            longitude = self._parse_coord(row.get('经度') or row.get('longitude'))
            latitude = self._parse_coord(row.get('纬度') or row.get('latitude'))
            if longitude is None or latitude is None:
                skipped_rows.append({'line': index, 'reason': '经纬度格式非法'})
                continue

            payload = {
                'name': (row.get('文物名称') or row.get('name') or '').strip(),
                'category': category,
                'level': level,
                'address': (row.get('详细地址') or row.get('address') or '').strip(),
                'longitude': longitude,
                'latitude': latitude,
                'manager': (row.get('管理单位') or row.get('manager') or '').strip(),
                'description': (row.get('现状描述') or row.get('description') or '').strip(),
                'protection_zone': (row.get('保护范围坐标') or row.get('protection_zone') or '').strip(),
                'control_zone': (row.get('建设控制地带坐标') or row.get('control_zone') or '').strip(),
            }

            if not payload['name']:
                skipped_rows.append({'line': index, 'reason': '缺少文物名称'})
                continue

            _, created = HeritageSite.objects.update_or_create(sip_code=sip_code, defaults=payload)
            if created:
                created_count += 1
            else:
                updated_count += 1

        return Response(
            {
                'success': True,
                'message': '导入完成',
                'data': {
                    'created_count': created_count,
                    'updated_count': updated_count,
                    'skipped_count': len(skipped_rows),
                    'skipped_rows': skipped_rows[:50],
                },
            }
        )

    def _parse_coord(self, value):
        text = str(value or '').strip()
        if not text:
            return None

        try:
            return float(text)
        except (TypeError, ValueError):
            pass

        try:
            nums = []
            current = ''
            for ch in text:
                if ch.isdigit() or ch in {'.', '-'}:
                    current += ch
                else:
                    if current:
                        nums.append(current)
                        current = ''
            if current:
                nums.append(current)
            if len(nums) >= 3:
                degree = float(nums[0])
                minute = float(nums[1])
                second = float(nums[2])
                return degree + minute / 60 + second / 3600
        except Exception:
            return None

        return None


class ImmovableHeritageExportAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        category = (request.GET.get('category') or '').strip()
        level = (request.GET.get('level') or '').strip()

        queryset = HeritageSite.objects.all().order_by('id')
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(sip_code__icontains=keyword)
                | Q(address__icontains=keyword)
                | Q(manager__icontains=keyword)
            )
        if category:
            queryset = queryset.filter(category=category)
        if level:
            queryset = queryset.filter(level=level)

        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        filename = timezone.now().strftime('immovable_heritage_%Y%m%d_%H%M%S.csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            '文物名称',
            '四普编号',
            '文物类别',
            '保护级别',
            '详细地址',
            '经度',
            '纬度',
            '管理单位',
            '保护范围坐标',
            '建设控制地带坐标',
            '现状描述',
        ])

        for item in queryset:
            writer.writerow([
                item.name,
                item.sip_code,
                item.get_category_display(),
                item.get_level_display(),
                item.address,
                item.longitude,
                item.latitude,
                item.manager,
                item.protection_zone or '',
                item.control_zone or '',
                item.description or '',
            ])

        return response


class InspectionListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        is_normal = (request.GET.get('is_normal') or '').strip().lower()
        page = max(int(request.GET.get('page', 1) or 1), 1)
        page_size = min(max(int(request.GET.get('page_size', 20) or 20), 1), 100)

        queryset = InspectionRecord.objects.select_related('site', 'inspector').order_by('-inspect_time')

        if keyword:
            queryset = queryset.filter(
                Q(site__name__icontains=keyword)
                | Q(site__sip_code__icontains=keyword)
                | Q(inspector__username__icontains=keyword)
                | Q(inspector__first_name__icontains=keyword)
                | Q(issue_details__icontains=keyword)
            )

        if is_normal in {'1', 'true', 'yes'}:
            queryset = queryset.filter(is_normal=True)
        elif is_normal in {'0', 'false', 'no'}:
            queryset = queryset.filter(is_normal=False)

        total = queryset.count()
        offset = (page - 1) * page_size
        rows = []
        for item in queryset[offset: offset + page_size]:
            rows.append(
                {
                    'id': item.id,
                    'site_id': item.site_id,
                    'site_name': item.site.name if item.site else '-',
                    'site_code': item.site.sip_code if item.site else '-',
                    'inspector_id': item.inspector_id,
                    'inspector_name': item.inspector.first_name or item.inspector.username,
                    'inspect_time': item.inspect_time.strftime('%Y-%m-%d %H:%M'),
                    'is_normal': item.is_normal,
                    'issue_details': item.issue_details or '',
                    'latitude': item.latitude,
                    'longitude': item.longitude,
                    'photo_url': request.build_absolute_uri(item.photo.url) if item.photo else '',
                }
            )

        return Response(
            {
                'success': True,
                'rows': rows,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                },
            }
        )


class InspectionStatsAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        total_count = InspectionRecord.objects.count()
        abnormal_count = InspectionRecord.objects.filter(is_normal=False).count()
        today = timezone.localdate()
        today_count = InspectionRecord.objects.filter(inspect_time__date=today).count()
        return Response(
            {
                'success': True,
                'data': {
                    'total_count': total_count,
                    'today_count': today_count,
                    'abnormal_count': abnormal_count,
                },
            }
        )


class InspectionDetailAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get_object(self, inspection_id):
        return InspectionRecord.objects.select_related('site', 'inspector').filter(id=inspection_id).first()

    def get(self, request, inspection_id):
        item = self.get_object(inspection_id)
        if not item:
            return Response({'success': False, 'message': '巡查记录不存在'}, status=404)

        return Response(
            {
                'success': True,
                'data': {
                    'id': item.id,
                    'site_id': item.site_id,
                    'site_name': item.site.name if item.site else '-',
                    'site_code': item.site.sip_code if item.site else '-',
                    'inspector_id': item.inspector_id,
                    'inspector_name': item.inspector.first_name or item.inspector.username,
                    'inspect_time': item.inspect_time.strftime('%Y-%m-%d %H:%M'),
                    'is_normal': item.is_normal,
                    'issue_details': item.issue_details or '',
                    'latitude': item.latitude,
                    'longitude': item.longitude,
                    'photo_url': request.build_absolute_uri(item.photo.url) if item.photo else '',
                },
            }
        )

    def patch(self, request, inspection_id):
        item = self.get_object(inspection_id)
        if not item:
            return Response({'success': False, 'message': '巡查记录不存在'}, status=404)

        if 'is_normal' in request.data:
            raw = str(request.data.get('is_normal')).strip().lower()
            item.is_normal = raw in {'1', 'true', 'yes', 'on'}
        if 'issue_details' in request.data:
            item.issue_details = (request.data.get('issue_details') or '').strip()
        item.save(update_fields=['is_normal', 'issue_details'])
        return Response({'success': True, 'message': '巡查记录已更新'})

    def delete(self, request, inspection_id):
        item = self.get_object(inspection_id)
        if not item:
            return Response({'success': False, 'message': '巡查记录不存在'}, status=404)
        item.delete()
        return Response({'success': True, 'message': '巡查记录已删除'})


class GisKmlRecordsAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        records = KmlUploadRecord.objects.select_related('uploaded_by').order_by('-created_at')[:200]
        rows = []
        for record in records:
            rows.append(
                {
                    'id': record.id,
                    'title': record.title,
                    'file_url': record.source_file.url if record.source_file else '',
                    'conflict_count': record.conflict_count,
                    'feature_count': record.feature_count,
                    'created_at': record.created_at.strftime('%Y-%m-%d %H:%M'),
                }
            )
        return Response({'success': True, 'rows': rows})


class _KmlContentResolverMixin:
    CACHE_SECONDS = 60 * 60

    def _cache_key(self, record):
        return f'gis_kml_text:{record.id}:{int(record.updated_at.timestamp())}'

    def _resolve_record_payload(self, record):
        cache_key = self._cache_key(record)
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            with record.source_file.open('rb') as source:
                raw_bytes = source.read()
        except Exception as exc:
            raise ValueError(f'读取源文件失败：{exc}')

        filename = (record.source_file.name or record.title or '').lower()

        try:
            if filename.endswith('.kmz') or filename.endswith('.ovkmz'):
                kml_bytes = self._extract_kml_from_kmz(raw_bytes)
                if not kml_bytes:
                    raise ValueError('KMZ 中未找到可解析的 KML 文件。')
                file_format = 'kmz'
            else:
                kml_bytes = raw_bytes
                file_format = 'kml'

            kml_text = self._decode_kml_bytes(kml_bytes)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f'解析失败：{exc}')

        payload = {
            'record_id': record.id,
            'title': record.title,
            'file_format': file_format,
            'kml_text': kml_text,
        }
        cache.set(cache_key, payload, self.CACHE_SECONDS)
        return payload

    def _extract_kml_from_kmz(self, raw_bytes):
        with zipfile.ZipFile(io.BytesIO(raw_bytes), 'r') as zf:
            names = zf.namelist()
            preferred = next((item for item in names if item.lower() == 'doc.kml'), None)
            if preferred:
                return zf.read(preferred)
            fallback = next((item for item in names if item.lower().endswith('.kml')), None)
            if fallback:
                return zf.read(fallback)
        return b''

    def _decode_kml_bytes(self, kml_bytes):
        head = kml_bytes[:512].decode('ascii', errors='ignore')
        match = re.search(r'encoding=["\']([A-Za-z0-9_\-]+)["\']', head)
        declared_enc = (match.group(1).lower() if match else '').strip()

        tried = []
        if declared_enc:
            tried.append(declared_enc)
        for enc in ('utf-8-sig', 'utf-8', 'gb18030'):
            if enc not in tried:
                tried.append(enc)

        for enc in tried:
            try:
                return kml_bytes.decode(enc)
            except Exception:
                continue
        return kml_bytes.decode('utf-8', errors='replace')


class GisKmlRecordKmlContentAPIView(_KmlContentResolverMixin, APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request, record_id):
        record = KmlUploadRecord.objects.filter(id=record_id).first()
        if not record or not record.source_file:
            return Response({'success': False, 'message': '记录不存在或未绑定源文件。'}, status=404)

        try:
            payload = self._resolve_record_payload(record)
        except ValueError as exc:
            return Response({'success': False, 'message': str(exc)}, status=400)

        return Response({'success': True, 'data': payload})


class GisKmlBatchKmlContentAPIView(_KmlContentResolverMixin, APIView):
    permission_classes = [IsManagementAdmin]

    def post(self, request):
        record_ids_raw = request.data.get('record_ids')
        if record_ids_raw is None:
            record_ids_raw = request.data.getlist('record_ids') if hasattr(request.data, 'getlist') else []

        if isinstance(record_ids_raw, str):
            text = record_ids_raw.strip()
            if text.startswith('['):
                try:
                    record_ids_raw = json.loads(text)
                except Exception:
                    record_ids_raw = []
            elif text:
                record_ids_raw = [chunk.strip() for chunk in text.split(',') if chunk.strip()]
            else:
                record_ids_raw = []

        if not isinstance(record_ids_raw, list):
            return Response({'success': False, 'message': 'record_ids 参数格式错误。'}, status=400)

        normalized_ids = []
        seen = set()
        for raw_id in record_ids_raw:
            try:
                rid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if rid <= 0 or rid in seen:
                continue
            seen.add(rid)
            normalized_ids.append(rid)

        if not normalized_ids:
            return Response({'success': False, 'message': '请提供至少一个有效 record_id。'}, status=400)

        records_map = {
            item.id: item
            for item in KmlUploadRecord.objects.filter(id__in=normalized_ids)
        }

        items = []
        failed_items = []
        for rid in normalized_ids:
            record = records_map.get(rid)
            if not record or not record.source_file:
                failed_items.append({'record_id': rid, 'message': '记录不存在或未绑定源文件。'})
                continue

            try:
                payload = self._resolve_record_payload(record)
                items.append(payload)
            except ValueError as exc:
                failed_items.append({'record_id': rid, 'message': str(exc)})

        return Response(
            {
                'success': True,
                'data': {
                    'items': items,
                    'failed_items': failed_items,
                    'total_count': len(normalized_ids),
                    'success_count': len(items),
                    'failed_count': len(failed_items),
                },
            }
        )


class GisKmlManagementActionAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        action = (request.data.get('action') or '').strip()
        threshold = legacy_views._normalize_threshold(request.data.get('threshold_m', 50))

        if action == 'upload':
            return self._handle_upload(request, threshold)
        if action == 'rename_record':
            return self._handle_rename(request)
        if action == 'delete_record':
            return self._handle_delete(request)
        if action == 'analyze_selected':
            return self._handle_analyze(request, threshold)
        if action in {'analyze_export_selected', 'export_conflict_kml', 'export_boundary_points', 'export_boundary_kmz'}:
            return self._handle_export(request, threshold, action)

        return Response({'success': False, 'message': '未知操作请求。'}, status=400)

    def _selected_records(self, request):
        single_record_id = (request.data.get('single_record_id') or '').strip()
        if single_record_id:
            selected_ids = [single_record_id]
        else:
            selected_ids = [sid for sid in request.data.getlist('selected_ids') if sid]

        if not selected_ids:
            return None, Response({'success': False, 'message': '请先选择要处理的记录。'}, status=400)

        records = list(KmlUploadRecord.objects.filter(id__in=selected_ids))
        if not records:
            return None, Response({'success': False, 'message': '未找到选中的文件记录。'}, status=404)

        return records, None

    def _handle_upload(self, request, threshold):
        immediate_analyze = str(request.data.get('immediate_analyze') or '1').lower() in {'1', 'true', 'on', 'yes'}
        upload_files = request.FILES.getlist('kml_files')
        if not upload_files:
            return Response({'success': False, 'message': '请至少选择一个KML/KMZ/OVKML/OVKMZ文件。'}, status=400)

        created_count = 0
        total_conflicts = 0
        warnings = []
        site_points = legacy_views._load_conflict_site_points() if immediate_analyze else None

        for upload in upload_files:
            name = upload.name or '未命名文件'
            lower_name = name.lower()
            if not (lower_name.endswith('.kml') or lower_name.endswith('.ovkml') or lower_name.endswith('.kmz') or lower_name.endswith('.ovkmz')):
                warnings.append(f'已跳过不支持的文件：{name}')
                continue

            record = KmlUploadRecord.objects.create(
                title=name,
                source_file=upload,
                uploaded_by=request.user,
                threshold_m=threshold,
                feature_count=0,
                conflict_count=0,
                report_json='',
            )

            if immediate_analyze:
                try:
                    with record.source_file.open('rb') as source:
                        content = source.read()
                    features = legacy_views._extract_features_from_upload(name, content)
                    conflicts = legacy_views._analyze_conflicts(features, threshold, site_points=site_points)
                except Exception as exc:
                    warnings.append(f'{name} 已上传，但即时分析失败：{exc}')
                else:
                    total_conflicts += len(conflicts)
                    report_payload = {
                        'threshold_m': threshold,
                        'feature_count': len(features),
                        'conflict_count': len(conflicts),
                        'generated_at': timezone.now().isoformat(),
                        'conflicts': conflicts,
                    }
                    record.feature_count = len(features)
                    record.conflict_count = len(conflicts)
                    record.report_json = json.dumps(report_payload, ensure_ascii=False)
                    record.save(update_fields=['feature_count', 'conflict_count', 'report_json', 'updated_at'])

            created_count += 1

        if created_count == 0:
            return Response({'success': False, 'message': '未成功上传任何可识别文件。', 'warnings': warnings}, status=400)

        message = (
            f'已上传并分析 {created_count} 个文件，共发现 {total_conflicts} 处冲突。'
            if immediate_analyze
            else f'已快速上传 {created_count} 个文件。'
        )
        return Response(
            {
                'success': True,
                'message': message,
                'data': {
                    'created_count': created_count,
                    'total_conflicts': total_conflicts,
                    'warnings': warnings,
                },
            }
        )

    def _handle_rename(self, request):
        record_id = (request.data.get('record_id') or '').strip()
        new_title = (request.data.get('new_title') or '').strip()

        if not record_id:
            return Response({'success': False, 'message': '缺少记录ID。'}, status=400)
        if not new_title:
            return Response({'success': False, 'message': '新名称不能为空。'}, status=400)
        if len(new_title) > 255:
            return Response({'success': False, 'message': '新名称长度不能超过255个字符。'}, status=400)

        record = KmlUploadRecord.objects.filter(id=record_id).first()
        if not record:
            return Response({'success': False, 'message': '要重命名的记录不存在。'}, status=404)

        record.title = new_title
        record.save(update_fields=['title', 'updated_at'])
        return Response({'success': True, 'message': f'已重命名为：{new_title}'})

    def _handle_delete(self, request):
        record_id = (request.data.get('record_id') or '').strip()
        if not record_id:
            return Response({'success': False, 'message': '缺少记录ID。'}, status=400)

        record = KmlUploadRecord.objects.filter(id=record_id).first()
        if not record:
            return Response({'success': False, 'message': '要删除的记录不存在。'}, status=404)

        if record.source_file:
            record.source_file.delete(save=False)
        record.delete()
        return Response({'success': True, 'message': 'KML 文件记录已删除。'})

    def _handle_analyze(self, request, threshold):
        records, error_response = self._selected_records(request)
        if error_response:
            return error_response

        force_reanalyze = str(request.data.get('force_reanalyze') or '').lower() in {'1', 'true', 'on', 'yes'}
        combined_conflicts, updated_count, failed_count, failed_items = legacy_views._reanalyze_kml_records(
            records,
            threshold,
            use_cache=not force_reanalyze,
        )

        return Response(
            {
                'success': True,
                'message': f'已按阈值 {threshold} 米完成查询，更新 {updated_count} 条记录，识别 {len(combined_conflicts)} 处冲突。',
                'data': {
                    'updated_count': updated_count,
                    'conflict_count': len(combined_conflicts),
                    'conflicts': combined_conflicts,
                    'failed_count': failed_count,
                    'failed_items': failed_items,
                },
            }
        )

    def _handle_export(self, request, threshold, action):
        records, error_response = self._selected_records(request)
        if error_response:
            return error_response

        force_reanalyze = str(request.data.get('force_reanalyze') or '').lower() in {'1', 'true', 'on', 'yes'}
        combined_conflicts, _updated_count, failed_count, failed_items = legacy_views._reanalyze_kml_records(
            records,
            threshold,
            use_cache=not force_reanalyze,
        )
        if failed_count:
            # 导出场景允许部分失败，成功部分仍可继续导出。
            pass

        if action == 'analyze_export_selected':
            return legacy_views._build_conflict_report_csv(combined_conflicts, threshold, records)
        if action == 'export_conflict_kml':
            return legacy_views._build_conflict_sites_kml(combined_conflicts, threshold, records)

        cookie = (request.data.get('sipu_cookie') or '').strip()
        if not cookie:
            return Response({'success': False, 'message': '请先填写四普系统的 Cookie。'}, status=400)
        if not combined_conflicts:
            return Response({'success': False, 'message': '所选文件中未发现冲突文物点，无需导出边界。'}, status=400)
        user_county = (request.data.get('sipu_county') or '').strip()

        if action == 'export_boundary_points':
            return legacy_views._build_boundary_points_csv(combined_conflicts, records, cookie, user_county)
        if action == 'export_boundary_kmz':
            return legacy_views._build_boundary_points_kmz(combined_conflicts, records, cookie, user_county)

        return Response(
            {
                'success': False,
                'message': '未知导出动作。',
                'data': {
                    'failed_count': failed_count,
                    'failed_items': failed_items,
                },
            },
            status=400,
        )


class GisKmlProcessConvertAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        tool = (request.data.get('tool') or '').strip()
        action = (request.data.get('action') or '').strip()

        if tool == 'dxf_to_kml':
            dxf_file = request.FILES.get('dxf_file')
            if not dxf_file:
                return Response({'success': False, 'message': '请先选择 DXF 文件。'}, status=400)

            lower_name = (dxf_file.name or '').lower()
            if not lower_name.endswith('.dxf'):
                return Response({'success': False, 'message': '文件格式不正确，请上传 .dxf 文件。'}, status=400)

            try:
                kml_bytes, _stats = legacy_views._convert_dxf_bytes_to_kml(
                    dxf_file.read(), os.path.splitext(dxf_file.name)[0]
                )
            except Exception as exc:
                return Response({'success': False, 'message': f'DXF 转换失败：{exc}'}, status=400)

            date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
            export_name = f'dxf_to_kml_{date_str}.kml'
            response = HttpResponse(kml_bytes, content_type='application/vnd.google-earth.kml+xml; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{export_name}"'
            return response

        if tool == 'kml_table':
            source_mode = (request.data.get('source_mode') or 'uploaded').strip()
            input_crs = (request.data.get('input_crs') or 'wgs84').strip()
            output_mode = (request.data.get('output_mode') or 'geo').strip()
            geo_output_crs = (request.data.get('geo_output_crs') or 'wgs84').strip()
            uploaded_record_id = (request.data.get('uploaded_record_id') or '').strip()

            source_name = ''
            raw_content = b''

            if source_mode == 'uploaded':
                if not uploaded_record_id:
                    return Response({'success': False, 'message': '请先选择已上传记录。'}, status=400)
                record = KmlUploadRecord.objects.filter(id=uploaded_record_id).first()
                if not record:
                    return Response({'success': False, 'message': '所选记录不存在。'}, status=404)
                source_name = os.path.basename(record.source_file.name or record.title or f'kml_record_{record.id}')
                with record.source_file.open('rb') as source:
                    raw_content = source.read()
            else:
                upload_file = request.FILES.get('kml_file')
                if not upload_file:
                    return Response({'success': False, 'message': '请先上传 KML/KMZ 文件。'}, status=400)
                source_name = upload_file.name or '未命名文件'
                raw_content = upload_file.read()

            if not legacy_views._is_kml_family_filename(source_name):
                return Response({'success': False, 'message': '文件格式不正确，请选择 .kml/.kmz/.ovkml/.ovkmz。'}, status=400)

            parse_output_crs = 'cgcs2000_proj' if output_mode == 'cgcs2000_proj' else geo_output_crs
            try:
                records, file_format = parse_kml_or_kmz(raw_content, input_crs=input_crs, output_crs=parse_output_crs)
            except Exception as exc:
                return Response({'success': False, 'message': f'解析失败：{exc}'}, status=400)

            if not records:
                return Response({'success': False, 'message': '未提取到要素，请检查文件内容。'}, status=400)

            table_rows = legacy_views._build_kml_table_rows(records, parse_output_crs)

            if action == 'export_csv':
                csv_text = legacy_views._build_kml_table_csv(table_rows, parse_output_crs)
                date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
                ext_name = 'cgcs2000坐标' if parse_output_crs == 'cgcs2000_proj' else '经纬度坐标'
                report_name = f'{date_str}_{os.path.splitext(source_name)[0]}_{ext_name}.csv'
                response = HttpResponse(csv_text, content_type='text/csv; charset=utf-8-sig')
                response['Content-Disposition'] = f'attachment; filename="{report_name}"'
                return response

            return Response(
                {
                    'success': True,
                    'data': {
                        'source_name': source_name,
                        'file_format': file_format,
                        'total_count': len(table_rows),
                        'preview_rows': table_rows[:200],
                        'preview_truncated': len(table_rows) > 200,
                        'coord_a_label': 'CGCS2000_X(米)' if parse_output_crs == 'cgcs2000_proj' else '经度',
                        'coord_b_label': 'CGCS2000_Y(米)' if parse_output_crs == 'cgcs2000_proj' else '纬度',
                    },
                }
            )

        return Response({'success': False, 'message': '未知操作请求。'}, status=400)


class GisOvkmlConvertAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload_file = request.FILES.get('ovkml_file')
        input_crs = (request.data.get('input_crs') or 'wgs84').strip()
        output_crs = (request.data.get('output_crs') or 'cgcs2000').strip()
        action = (request.data.get('action') or 'convert').strip()
        deduplicate = str(request.data.get('deduplicate') or 'true').lower() in {'1', 'true', 'on', 'yes'}

        if not upload_file:
            return Response({'success': False, 'message': '请先选择 KML/KMZ/OVKML/OVKMZ 文件。'}, status=400)

        filename = (upload_file.name or '').lower()
        if not (filename.endswith('.kml') or filename.endswith('.ovkml') or filename.endswith('.kmz') or filename.endswith('.ovkmz')):
            return Response({'success': False, 'message': '文件格式不正确，请上传 .kml .kmz .ovkml .ovkmz 文件。'}, status=400)

        try:
            records, file_format = parse_kml_or_kmz(upload_file.read(), input_crs=input_crs, output_crs=output_crs)
        except Exception as exc:
            return Response({'success': False, 'message': f'解析失败：{exc}'}, status=400)

        if not records:
            return Response({'success': False, 'message': '未提取到 Placemark，请检查文件内容。'}, status=400)

        project_csv, detail_csv = build_csv_outputs(records)

        export_dir = os.path.join(settings.MEDIA_ROOT, 'ovkml_exports')
        os.makedirs(export_dir, exist_ok=True)
        export_id = uuid.uuid4().hex
        project_filename = f'{export_id}_projectaudit.csv'
        detail_filename = f'{export_id}_detail.csv'
        project_path = os.path.join(export_dir, project_filename)
        detail_path = os.path.join(export_dir, detail_filename)

        with open(project_path, 'w', encoding='utf-8-sig', newline='') as project_file:
            project_file.write(project_csv)
        with open(detail_path, 'w', encoding='utf-8-sig', newline='') as detail_file:
            detail_file.write(detail_csv)

        preview_rows = []
        for item in records[:100]:
            preview_rows.append(
                {
                    'project_name': item.project_name,
                    'geometry_type': item.geometry_type,
                    'vertex_count': item.vertex_count,
                    'project_lon': '' if item.target_lon is None else f'{item.target_lon:.10f}',
                    'project_lat': '' if item.target_lat is None else f'{item.target_lat:.10f}',
                    'cgcs2000_x': '' if item.cgcs2000_x is None else f'{item.cgcs2000_x:.3f}',
                    'cgcs2000_y': '' if item.cgcs2000_y is None else f'{item.cgcs2000_y:.3f}',
                    'source_folder': item.source_folder,
                }
            )

        import_count = 0
        skipped_count = 0
        if action == 'import':
            existing_keys = set()
            if deduplicate:
                for item in ProjectAudit.objects.only('project_name', 'project_lon', 'project_lat'):
                    lon_key = '' if item.project_lon is None else f'{item.project_lon:.6f}'
                    lat_key = '' if item.project_lat is None else f'{item.project_lat:.6f}'
                    existing_keys.add((item.project_name.strip(), lon_key, lat_key))

            batch_seen = set()
            to_create = []
            for item in records:
                lon_key = '' if item.target_lon is None else f'{item.target_lon:.6f}'
                lat_key = '' if item.target_lat is None else f'{item.target_lat:.6f}'
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
                        remarks=(
                            f'来源文件夹:{item.source_folder or "-"}; 几何:{item.geometry_type}; '
                            f'顶点:{item.vertex_count}; 导入来源:KML/KMZ转换工具'
                        ),
                        received_date=timezone.now(),
                    )
                )

            if to_create:
                ProjectAudit.objects.bulk_create(to_create)
            import_count = len(to_create)

        return Response(
            {
                'success': True,
                'data': {
                    'total_count': len(records),
                    'preview_rows': preview_rows,
                    'preview_truncated': len(records) > 100,
                    'file_format': file_format,
                    'project_csv_url': f"{settings.MEDIA_URL}ovkml_exports/{project_filename}",
                    'detail_csv_url': f"{settings.MEDIA_URL}ovkml_exports/{detail_filename}",
                    'import_done': action == 'import',
                    'import_count': import_count,
                    'import_skipped_count': skipped_count,
                },
            }
        )
