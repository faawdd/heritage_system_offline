# core/views.py
from django.shortcuts import render
from django.template.loader import render_to_string
from .models import HeritageSite, InspectionRecord, ProjectAudit, Coordinate
from .ovkml_converter import parse_ovkml, build_csv_outputs
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.conf import settings
from docxtpl import DocxTemplate
import os
import io
import zipfile
import uuid

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


@staff_member_required
def kml_overlay_check_view(request):
    """KML叠加检查页面"""
    sites = HeritageSite.objects.all()
    sites_data = []
    for site in sites:
        sites_data.append({
            "name": site.name,
            "lng": float(site.longitude),
            "lat": float(site.latitude),
            "level": site.level
        })

    context = {
        'sites_json': json.dumps(sites_data),
        'title': 'KML叠加检查'
    }
    return render(request, 'admin/kml_overlay_check.html', context)


@staff_member_required
def ovkml_converter_view(request):
    """OVKML 网页转换工具：提取坐标并导出可导入 ProjectAudit 的 CSV。"""
    context = {
        'title': 'OVKML转换导入',
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
            context['error'] = '请先选择 OVKML/KML 文件。'
            return render(request, 'admin/ovkml_converter.html', context)

        filename = (upload_file.name or '').lower()
        if not (filename.endswith('.kml') or filename.endswith('.ovkml')):
            context['error'] = '文件格式不正确，请上传 .kml 或 .ovkml 文件。'
            return render(request, 'admin/ovkml_converter.html', context)

        try:
            records = parse_ovkml(upload_file.read(), input_crs=input_crs, output_crs=output_crs)
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
                        remarks=f"来源文件夹:{item.source_folder or '-'}; 几何:{item.geometry_type}; 顶点:{item.vertex_count}; 导入来源:OVKML转换工具",
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
    """统计仪表板视图"""
    # 按分类统计
    category_stats = HeritageSite.objects.values('category').annotate(count=Count('id'))
    category_data = {
        'labels': [dict(HeritageSite.CATEGORY_CHOICES).get(cat['category'], cat['category']) 
                   for cat in category_stats],
        'data': [cat['count'] for cat in category_stats]
    }
    
    # 按保护等级统计
    level_stats = HeritageSite.objects.values('level').annotate(count=Count('id'))
    level_data = {
        'labels': [dict(HeritageSite.LEVEL_CHOICES).get(lev['level'], lev['level']) 
                   for lev in level_stats],
        'data': [lev['count'] for lev in level_stats]
    }
    
    # 总数统计
    total = HeritageSite.objects.count()
    
    context = {
        'category_stats_json': json.dumps(category_data),
        'level_stats_json': json.dumps(level_data),
        'total_sites': total,
        'title': '文物统计仪表板'
    }
    return render(request, 'admin/heritage_dashboard.html', context)


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

