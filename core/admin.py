from django.contrib import admin
from .models import HeritageSite, InspectionRecord, ProjectAudit, Coordinate, UserProfile, UserManagementAudit
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.utils.html import format_html, mark_safe
from django.contrib import messages
import csv
from django.http import HttpResponse, FileResponse, HttpResponseRedirect
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
import os
import zipfile
import io
from .utils import generate_word_log
import json
from django.shortcuts import render
import re
from django.conf import settings
from django.utils import timezone
from docxtpl import DocxTemplate




# 度分秒转十进制函数
def dms_to_decimal(dms_str):
    if not dms_str or not isinstance(dms_str, str):
        return dms_str
    try:
        # 正则提取：度、分、秒
        parts = re.findall(r"(\d+\.?\d*)", dms_str)
        if len(parts) >= 3:
            d = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return d + m/60 + s/3600
        return float(dms_str) # 如果已经是十进制则直接返回
    except:
        return None

class HeritageResource(resources.ModelResource):
    # 手动定义每一个字段，确保 attribute (模型) 和 column_name (Excel) 强绑定
    name = fields.Field(attribute='name', column_name='文物名称')
    sip_code = fields.Field(attribute='sip_code', column_name='四普编号')
    category = fields.Field(attribute='category', column_name='文物类别')
    level = fields.Field(attribute='level', column_name='保护级别')
    address = fields.Field(attribute='address', column_name='详细地址')
    longitude = fields.Field(attribute='longitude', column_name='经度')
    latitude = fields.Field(attribute='latitude', column_name='纬度')
    manager = fields.Field(attribute='manager', column_name='管理单位')
    protection_zone = fields.Field(attribute='protection_zone', column_name='保护范围坐标')
    control_zone = fields.Field(attribute='control_zone', column_name='建设控制地带坐标')
    description = fields.Field(attribute='description', column_name='现状描述')

    class Meta:
        model = HeritageSite
        # 排除 ID 列
        exclude = ('id',)
        # 使用四普编号作为唯一判定依据，防止重复导入
        import_id_fields = ('sip_code',)
        # 必须列出所有字段
        fields = ('name', 'sip_code', 'category', 'level', 'address', 'longitude', 'latitude', 
                  'manager', 'protection_zone', 'control_zone', 'description')

    def before_import_row(self, row, **kwargs):
        # 1. 坐标转换逻辑
        row['经度'] = dms_to_decimal(row.get('经度'))
        row['纬度'] = dms_to_decimal(row.get('纬度'))

        # 2. 手动将中文值映射为数据库的“代码”
        # 定义转换字典
        category_map = {v: k for k, v in HeritageSite.CATEGORY_CHOICES}
        level_map = {v: k for k, v in HeritageSite.LEVEL_CHOICES}

        # 执行转换
        raw_cat = str(row.get('文物类别', '')).strip()
        raw_lvl = str(row.get('保护级别', '')).strip()

        if raw_cat in category_map:
            row['文物类别'] = category_map[raw_cat]
        
        if raw_lvl in level_map:
            row['保护级别'] = level_map[raw_lvl]

        # 3. 清洗表头空格
        new_row = {str(k).strip(): v for k, v in row.items() if k}
        row.clear()
        row.update(new_row)

# 创建坎儿井专项管理类 - 基于名称包含"坎儿井"进行过滤
class KanerjingFilter(admin.SimpleListFilter):
    title = '坎儿井过滤'
    parameter_name = 'is_kanerjing'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', '仅显示坎儿井'),
            ('no', '不显示坎儿井'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(name__contains='坎儿井')
        if self.value() == 'no':
            return queryset.exclude(name__contains='坎儿井')

@admin.register(HeritageSite)
class HeritageAdmin(ImportExportModelAdmin):
# 注意：这里只能写 HeritageSite 模型里有的字段
    resource_class = HeritageResource
    change_list_template = 'admin/core/heritagesite/change_list.html'
    list_display = ('sip_code', 'name', 'address', 'category', 'level', 'manager')
    list_display_links = None
    list_filter = ('category', 'level', KanerjingFilter)
    search_fields = ('name', 'sip_code', 'address')
    list_editable = ('address', 'manager')

    def changelist_view(self, request, extra_context=None):
        if request.method == 'POST' and '_save' in request.POST:
            if request.POST.get('edit_mode') != '1':
                self.message_user(request, '当前为查看模式，请先点击“进入编辑模式”后再保存。', level=messages.WARNING)
                return HttpResponseRedirect(request.get_full_path())
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        """获取查询集"""
        qs = super().get_queryset(request)
        return qs
    
    def has_add_permission(self, request):
        """权限检查：仅管理员及以上可以添加"""
        from core.permission_decorators import is_admin
        if not is_admin(request.user):
            return False
        return super().has_add_permission(request)
    
    def has_change_permission(self, request, obj=None):
        """权限检查：仅管理员及以上可以编辑"""
        from core.permission_decorators import is_admin
        if not is_admin(request.user):
            return False
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        """权限检查：仅超级管理员可以删除"""
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
    
    def identify_kanerjing(self, request, queryset):
        """识别坎儿井数据的管理操作"""
        kanerjing_count = 0
        for obj in queryset:
            if '坎儿井' in obj.name:
                kanerjing_count += 1
        
        self.message_user(request, f'检查完成！在选中的 {queryset.count()} 条记录中找到 {kanerjing_count} 处坎儿井')
    identify_kanerjing.short_description = '检查并识别坎儿井（名称包含"坎儿井"）'
    
    actions = ['identify_kanerjing']


@admin.register(InspectionRecord)
class InspectionAdmin(admin.ModelAdmin):
    """巡查记录管理 - 权限说明
    
    看护员：可添加/编辑自己的记录，不能删除
    管理员：完全管理所有记录
    超级管理员：完全访问
    """
    list_display = ('site', 'inspector_display', 'inspect_time', 'is_normal', 'display_photo', 'issue_summary')
    list_filter = ('is_normal', 'inspect_time', 'inspector')
    raw_id_fields = ('site',)
    search_fields = ('site__name', 'inspector__username', 'inspector__first_name')
    readonly_fields = ('display_photo', 'inspect_time')  # 基础必读字段
    date_hierarchy = 'inspect_time'
    
    fieldsets = (
        ('巡查基本信息', {
            'fields': ('site', 'inspector', 'inspect_time'),
            'description': '权限说明：看护员的巡查员字段自动锁定，管理员可修改'
        }),
        ('巡查结果', {
            'fields': ('is_normal', 'issue_details'),
            'description': '记录巡查发现的问题或确认文物安全'
        }),
        ('现场证据', {
            'fields': ('photo', 'display_photo'),
            'description': '上传现场照片为必选。备注：带经纬度时间水印',
            'classes': ('collapse',),
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        photo_field = form.base_fields.get('photo')
        if photo_field:
            photo_field.help_text = '备注：带经纬度时间水印'
            photo_field.required = obj is None
        return form

    def inspector_display(self, obj):
        """格式化显示巡查员：优先显示姓名，否则显示账号"""
        if obj.inspector.first_name:
            return f"{obj.inspector.first_name} ({obj.inspector.username})"
        return obj.inspector.username
    inspector_display.short_description = '巡查员'

    def get_readonly_fields(self, request, obj=None):
        """
        根据用户权限动态设置只读字段
        - 看护员用户：inspector 字段只读（锁定为自己）
        - 管理员用户：inspector 字段可编辑
        - 超级管理员：所有字段可编辑
        """
        readonly = list(self.readonly_fields)
        
        # 检查用户是否属于"文物看护员"用户组
        is_inspector = request.user.groups.filter(name='文物看护员').exists()
        
        if is_inspector:
            # 看护员用户：inspector 字段添加到只读列表
            if 'inspector' not in readonly:
                readonly.append('inspector')
        # 管理员等其他用户：inspector 字段可编辑（不需要添加到只读列表）
        
        return readonly
    
    def has_add_permission(self, request):
        """权限检查：看护员和管理员都可以添加"""
        from core.permission_decorators import is_inspector, is_admin
        if is_inspector(request.user) or is_admin(request.user):
            return super().has_add_permission(request)
        return False
    
    def has_change_permission(self, request, obj=None):
        """权限检查：看护员只能修改自己的记录"""
        from core.permission_decorators import is_admin
        
        if is_admin(request.user):
            return super().has_change_permission(request, obj)
        
        is_inspector = request.user.groups.filter(name='文物看护员').exists()
        if is_inspector and obj and obj.inspector != request.user:
            return False
        
        return super().has_change_permission(request, obj) if is_inspector else False
    
    def has_delete_permission(self, request, obj=None):
        """权限检查：仅管理员及以上可以删除"""
        from core.permission_decorators import is_admin
        if not is_admin(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def issue_summary(self, obj):
        """显示问题简述"""
        if obj.is_normal:
            return mark_safe('<span style="color: green;">✓ 正常</span>')
        else:
            summary = obj.issue_details[:30] if obj.issue_details else '有问题'
            return format_html(
                '<span style="color: red;">⚠️ 发现问题</span><br><small>{}</small>',
                summary
            )
    issue_summary.short_description = '巡查情况'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """自定义外键字段的显示格式"""
        if db_field.name == 'inspector':
            # 只显示文物看护员用户组中的用户
            from django.contrib.auth.models import Group, User
            try:
                group = Group.objects.get(name='文物看护员')
                kwargs['queryset'] = User.objects.filter(groups=group).order_by('first_name', 'username')
            except Group.DoesNotExist:
                pass
            
            # 自定义标签显示格式：显示 "姓名 (账号)" 或 "账号"
            def label_from_instance(obj):
                if obj.first_name:
                    return f"{obj.first_name} ({obj.username})"
                return obj.username
            
            form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            form_field.label_from_instance = label_from_instance
            return form_field
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def display_photo(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="200" style="border-radius: 4px;" /><br><a href="{}" target="_blank">查看原图</a>',
                obj.photo.url,
                obj.photo.url
            )
        return "无照片"
    display_photo.short_description = "现场照片"

    def get_queryset(self, request):
        """
        根据用户权限过滤查询集
        - 超级管理员和管理员：查看所有巡查记录
        - 文物看护员：只能查看自己的巡查记录
        """
        qs = super().get_queryset(request)
        
        # 检查用户权限
        is_admin = request.user.is_superuser or request.user.groups.filter(name='管理员').exists()
        is_inspector = request.user.groups.filter(name='文物看护员').exists()
        
        if is_admin:
            # 管理员可以查看所有记录
            return qs
        elif is_inspector:
            # 看护员只能看自己的记录
            return qs.filter(inspector=request.user)
        
        return qs

    def save_model(self, request, obj, form, change):
        """
        保存前处理 inspector 字段
        - 看护员用户新建时：强制设置为当前用户
        - 管理员用户：允许自由指定（表单已提交的值）
        """
        is_inspector = request.user.groups.filter(name='文物看护员').exists()
        
        if not change:  # 新建记录
            if is_inspector:
                # 看护员用户：强制设置为当前登录用户
                obj.inspector = request.user
            # 管理员等用户：使用表单中提交的值（或默认为当前用户）
            elif not obj.inspector:
                obj.inspector = request.user
        
        super().save_model(request, obj, form, change)

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="inspection_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(['文物名称', '巡查员', '巡查时间', '是否正常', '问题描述'])
        for obj in queryset:
            writer.writerow([
                obj.site.name, 
                obj.inspector.get_full_name() or obj.inspector.username, 
                obj.inspect_time.strftime('%Y-%m-%d %H:%M'),
                '正常' if obj.is_normal else '异常',
                obj.issue_details or ''
            ])
        return response
    export_as_csv.short_description = "导出为 CSV"

    def batch_export_word(self, request, queryset):
        if queryset.count() == 0:
            self.message_user(request, '请先选择至少一条记录', level='error')
            return
            
        byte_io = io.BytesIO()
        with zipfile.ZipFile(byte_io, 'w') as zip_file:
            for record in queryset:
                try:
                    file_path = generate_word_log(record)
                    zip_file.write(file_path, os.path.basename(file_path))
                except Exception as e:
                    self.message_user(request, f'导出 {record.site.name} 失败: {str(e)}', level='error')
        
        if byte_io.tell() > 0:
            byte_io.seek(0)
            response = HttpResponse(byte_io, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="巡查记录汇总.zip"'
            return response
        else:
            self.message_user(request, '没有可导出的内容', level='warning')

    batch_export_word.short_description = "批量导出为 Word"
    actions = ['export_as_csv', 'batch_export_word']

class CoordinateInline(admin.TabularInline):
    model = Coordinate
    verbose_name = '项目建设区转点坐标'
    verbose_name_plural = '项目建设区转点坐标'
    extra = 0
    fields = (
        'tower_no',
        'cgcs2000_x',
        'cgcs2000_y',
        'longitude',
        'latitude',
        'is_on_boundary',
        'check_status',
        'remark',
    )
    show_change_link = True

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'tower_no' and formfield:
            formfield.label = '转点坐标'
        return formfield


@admin.register(ProjectAudit)
class ProjectAdmin(admin.ModelAdmin):
    """项目建设审批管理 - 权限说明
    
    看护员：无权访问
    管理员：完全管理所有项目
    超级管理员：完全访问
    """
    list_display = ('project_name', 'project_unit', 'workflow_status_display', 'alert_status', 'received_date')
    list_filter = ('workflow_status', 'is_in_protection_zone', 'is_in_control_zone', 'received_date')
    search_fields = ('project_name', 'project_unit', 'archive_number')
    readonly_fields = ('is_in_protection_zone', 'is_in_control_zone', 'received_date')
    date_hierarchy = 'received_date'
    inlines = [CoordinateInline]
    
    fieldsets = (
        ('基础信息（标题、字号）', {
            'fields': (
                'project_name',
                'archive_number',
                'workflow_status',
                'received_date',
            )
        }),
        ('工程概况（地址、规模）', {
            'fields': (
                'project_unit',
                'construction_content',
                'project_scale',
                'related_site',
            )
        }),
        ('坐标定位信息', {
            'fields': (
                'project_lon',
                'project_lat',
                'project_coordinates',
                'is_in_protection_zone',
                'is_in_control_zone',
                'survey_conclusion',
            )
        }),
        ('阶段1：项目方提交查询函', {
            'fields': ('inquiry_letter', 'ovital_kml_file'),
            'classes': ('collapse',)
        }),
        ('阶段2：奥维查询', {
            'fields': ('ovital_query_record', 'ovital_query_date'),
            'classes': ('collapse',)
        }),
        ('阶段3：现场勘察', {
            'fields': ('site_survey_record', 'site_survey_photos', 'site_survey_date'),
            'classes': ('collapse',)
        }),
        ('阶段4：上报市文物局', {
            'fields': ('application_report', 'application_date'),
            'classes': ('collapse',)
        }),
        ('阶段5：市文物局审批', {
            'fields': ('bureau_approval_reply', 'bureau_approval_date', 'bureau_opinion'),
            'classes': ('collapse',)
        }),
        ('阶段6：回函项目方', {
            'fields': ('project_reply_letter', 'project_reply_date'),
            'classes': ('collapse',)
        }),
        ('归档管理', {
            'fields': ('archived_date',),
            'classes': ('collapse',)
        }),
        ('其他信息', {
            'fields': ('remarks', 'audit_opinion', 'status', 'file_archive'),
            'classes': ('collapse',)
        }),
    )

    def workflow_status_display(self, obj):
        status_colors = {
            'received': '#17a2b8',
            'ovital_checked': '#007bff',
            'site_surveyed': '#6f42c1',
            'application_submitted': '#fd7e14',
            'bureau_approved': '#28a745',
            'replied_to_project': '#20c997',
            'archived': '#6c757d',
        }
        color = status_colors.get(obj.workflow_status, '#6c757d')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">● {obj.get_workflow_status_display()}</span>')
    
    workflow_status_display.short_description = "当前状态"

    def alert_status(self, obj):
        if obj.is_in_protection_zone:
            return mark_safe('<span style="color: red; font-weight: bold;">⚠️ 侵入保护范围 (禁建区)</span>')
        elif obj.is_in_control_zone:
            return mark_safe('<span style="color: orange; font-weight: bold;">⚠️ 位于建控地带</span>')
        return mark_safe('<span style="color: green;">✅ 安全距离</span>')
    
    alert_status.short_description = "两线预警状态"

    def has_module_permission(self, request):
        """权限检查：看护员无权访问项目管理模块"""
        from core.permission_decorators import is_admin
        return is_admin(request.user)
    
    def has_view_permission(self, request):
        """权限检查：仅管理员及以上可以查看"""
        from core.permission_decorators import is_admin
        return is_admin(request.user)
    
    def has_add_permission(self, request):
        """权限检查：仅管理员及以上可以添加"""
        from core.permission_decorators import is_admin
        return is_admin(request.user)
    
    def has_change_permission(self, request, obj=None):
        """权限检查：仅管理员及以上可以编辑"""
        from core.permission_decorators import is_admin
        return is_admin(request.user)
    
    def has_delete_permission(self, request, obj=None):
        """权限检查：仅管理员及以上可以删除"""
        from core.permission_decorators import is_admin
        return is_admin(request.user)

    def export_standard_request_doc(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '请只选择 1 条项目记录进行公文导出。', level=messages.WARNING)
            return

        project = queryset.first()
        try:
            template_candidates = [
                os.path.join(settings.BASE_DIR, '上行文 {{ file_id }} {{project_name}}.docx'),
                os.path.join(settings.BASE_DIR, '上行文_模板.docx'),
            ]
            template_path = next((path for path in template_candidates if os.path.exists(path)), None)
            if not template_path:
                self.message_user(request, f'模板不存在：{template_candidates[0]}', level=messages.ERROR)
                return

            doc = DocxTemplate(template_path)
            coordinates = project.coordinates.all().order_by('tower_no')

            issue_date = project.application_date or project.received_date or timezone.now()
            file_id = project.archive_number or f"鄯文旅字〔{issue_date.year}〕{project.id}号"

            context = {
                'project_name': project.project_name,
                'file_id': file_id,
                'file_no': file_id,
                'coordinates': [
                    {
                        'tower_no': item.tower_no,
                        'x': item.cgcs2000_x or '',
                        'y': item.cgcs2000_y or '',
                        'lon': item.longitude or '',
                        'lat': item.latitude or '',
                    }
                    for item in coordinates
                ],
                'issue_date': f'{issue_date.year}年{issue_date.month}月{issue_date.day}日',
            }

            doc.render(context)
            output = io.BytesIO()
            doc.save(output)
            output.seek(0)

            filename = f'标准请示公文_{project.project_name}.docx'
            return FileResponse(
                output,
                as_attachment=True,
                filename=filename,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        except Exception as exc:
            self.message_user(request, f'导出失败：{exc}', level=messages.ERROR)

    export_standard_request_doc.short_description = '导出标准请示公文'
    actions = ['export_standard_request_doc']

    class Media:
        js = ('admin/js/project_quick_nav.js',)


@admin.register(Coordinate)
class CoordinateAdmin(admin.ModelAdmin):
    list_display = (
        'project',
        'tower_no',
        'cgcs2000_x',
        'cgcs2000_y',
        'boundary_label',
        'check_status',
        'map_preview',
    )
    list_filter = ('is_on_boundary', 'check_status', 'project')
    search_fields = ('project__project_name', 'tower_no', 'remark')

    def boundary_label(self, obj):
        if obj.is_on_boundary:
            return mark_safe('<span class="el-tag el-tag--danger el-tag--mini">边界内</span>')
        return mark_safe('<span class="el-tag el-tag--success el-tag--mini">边界外</span>')

    boundary_label.short_description = '边界状态'

    def map_preview(self, obj):
        location_text = (
            f'杆塔号：{obj.tower_no}\\n'
            f'CGCS2000：X={obj.cgcs2000_x or "--"}, Y={obj.cgcs2000_y or "--"}\\n'
            f'经纬度：{obj.longitude or "--"}, {obj.latitude or "--"}\\n'
            f'说明：{obj.remark or "无"}'
        )
        return format_html(
            '<a href="javascript:void(0);" onclick="alert(\'{}\')">地图预览</a>',
            location_text.replace("'", "\\\\'")
        )

    map_preview.short_description = '地图预览'



# 修改后台左上角显示的文字
admin.site.site_header = '鄯善县文物数字化管理平台'

# 修改浏览器标签页显示的文字
admin.site.site_title = '基层文物管理系统'

# 修改后台首页的欢迎提示文字
admin.site.index_title = '欢迎使用文物安全巡查与项目管理系统'


# ============ 用户和组权限管理 ============

class CustomUserAdmin(BaseUserAdmin):
    """优化的用户管理界面 - 支持实时权限调整"""
    list_display = ('username', 'get_full_name', 'email', 'is_staff', 'is_active', 'get_groups', 'last_login')
    list_filter = ('is_staff', 'is_active', 'groups', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    readonly_fields = ('last_login', 'date_joined')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {
            'fields': ('first_name', 'last_name', 'email'),
            'classes': ('wide',)
        }),
        ('权限与用户组', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
            'description': '☝️ 在"用户组"中选择用户所属的组，每个组对应不同的权限级别。修改后立即生效。',
            'classes': ('wide',)
        }),
        ('重要日期', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('个人信息（可选）', {
            'classes': ('collapse',),
            'fields': ('first_name', 'last_name', 'email'),
        }),
        ('权限设置', {
            'fields': ('is_active', 'groups'),
            'description': '✓ 新用户默认为非活跃状态。请选择用户组后激活账户。',
        }),
    )

    def get_full_name(self, obj):
        """显示全名或用户名"""
        return obj.get_full_name() or '---'
    get_full_name.short_description = '姓名'

    def get_groups(self, obj):
        """显示用户所属组，超级管理员用特殊标记"""
        groups = list(obj.groups.all())
        if obj.is_superuser:
            return mark_safe('<span style="color: #f57c00; font-weight: bold;">👑 超级管理员</span>')
        if not groups:
            return '---'
        return ', '.join([f'<span style="background: #e3f2fd; padding: 2px 6px; border-radius: 3px; margin-right: 4px;">{g.name}</span>' for g in groups])
    get_groups.short_description = '用户组'

    def has_add_permission(self, request):
        """只有超级管理员可以添加用户"""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """只有超级管理员可以修改用户"""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """只有超级管理员可以删除用户"""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """只有超级管理员和管理员可以查看用户列表"""
        return request.user.is_superuser or request.user.groups.filter(name='管理员').exists()

    def get_queryset(self, request):
        """超级管理员可以看到所有用户，管理员只能看到非超级管理员的用户"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # 管理员看不到超级管理员和其他管理员
            qs = qs.exclude(is_superuser=True).exclude(groups__name='管理员')
        return qs

    def save_model(self, request, obj, form, change):
        """保存用户时生成或更新UserProfile，并记录操作"""
        super().save_model(request, obj, form, change)
        # 确保每个用户都有profile记录
        from core.models import UserProfile
        UserProfile.objects.get_or_create(user=obj)
        
        # 记录操作日志
        action = "修改用户" if change else "新建用户"
        self._log_action(request, obj, action)

    def delete_model(self, request, obj):
        """删除用户前记录日志"""
        self._log_action(request, obj, "删除用户")
        super().delete_model(request, obj)

    def _log_action(self, request, obj, action):
        """记录用户管理操作"""
        try:
            from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
            from django.contrib.contenttypes.models import ContentType
            
            action_flag = {
                "新建用户": ADDITION,
                "修改用户": CHANGE,
                "删除用户": DELETION,
            }.get(action, CHANGE)
            
            LogEntry.objects.create(
                user=request.user,
                content_type=ContentType.objects.get_for_model(User),
                object_id=obj.pk,
                object_repr=str(obj),
                action_flag=action_flag,
                change_message=f"{action}: {obj.username}"
            )
        except Exception:
            pass


class CustomGroupAdmin(BaseGroupAdmin):
    """优化的用户组管理界面 - 支持实时权限调整"""
    list_display = ('name', 'get_description', 'get_permission_count', 'get_members_count')
    filter_horizontal = ('permissions',)
    search_fields = ('name',)
    readonly_fields = ('get_members_list',)

    fieldsets = (
        ('用户组信息', {
            'fields': ('name', 'get_members_list'),
        }),
        ('权限配置', {
            'fields': ('permissions',),
            'description': '✓ 选择此用户组拥有的权限。修改后立即生效。',
        }),
    )

    def get_description(self, obj):
        """显示用户组描述"""
        descriptions = {
            '超级管理员': '🔑 最高权限',
            '管理员': '🔧 系统管理',
            '文物看护员': '👷 巡查员工',
        }
        return descriptions.get(obj.name, '用户组')
    get_description.short_description = '描述'

    def get_permission_count(self, obj):
        """权限数量"""
        return obj.permissions.count()
    get_permission_count.short_description = '权限数'

    def get_members_count(self, obj):
        """组成员数量"""
        return obj.user_set.count()
    get_members_count.short_description = '成员数'

    def get_members_list(self, obj):
        """显示用户组内的全部成员"""
        members = obj.user_set.all()
        if not members:
            return '（无成员）'
        
        member_html = '<ul style="margin: 10px 0;">'
        for user in members:
            icon = '👑' if user.is_superuser else '✓'
            member_html += f'<li>{icon} {user.get_full_name() or user.username} <small>({user.username})</small></li>'
        member_html += '</ul>'
        return mark_safe(member_html)
    get_members_list.short_description = '成员列表'

    def has_add_permission(self, request):
        """只有超级管理员可以创建新用户组"""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """只有超级管理员可以修改用户组"""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """只有超级管理员可以删除用户组"""
        if obj and obj.user_set.exists():
            # 不允许删除有成员的用户组
            return False
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """只有超级管理员和管理员可以查看用户组列表"""
        return request.user.is_superuser or request.user.groups.filter(name='管理员').exists()

    def save_model(self, request, obj, form, change):
        """保存用户组时记录操作"""
        super().save_model(request, obj, form, change)
        self._log_action(request, obj, change)

    def delete_model(self, request, obj):
        """删除用户组前检查并记录日志"""
        if obj.user_set.exists():
            from django.contrib import messages
            messages.error(request, f'无法删除用户组"{obj.name}"，因为它仍有 {obj.user_set.count()} 个成员。请先移除所有成员。')
            return
        self._log_action(request, obj, False, is_delete=True)
        super().delete_model(request, obj)

    def _log_action(self, request, obj, change, is_delete=False):
        """记录用户组管理操作"""
        try:
            from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
            from django.contrib.contenttypes.models import ContentType
            
            if is_delete:
                action_flag = DELETION
                message = f"删除用户组: {obj.name}"
            elif change:
                action_flag = CHANGE
                message = f"修改用户组: {obj.name}"
            else:
                action_flag = ADDITION
                message = f"新建用户组: {obj.name}"
            
            LogEntry.objects.create(
                user=request.user,
                content_type=ContentType.objects.get_for_model(Group),
                object_id=obj.pk,
                object_repr=str(obj),
                action_flag=action_flag,
                change_message=message
            )
        except Exception:
            pass


class UserProfileAdmin(admin.ModelAdmin):
    """用户密码修改记录和登录状态管理"""
    list_display = ('get_user_display', 'get_groups_display', 'has_changed_password', 'first_login_at', 'status_indicator')
    list_filter = ('has_changed_password', 'created_at', 'first_login_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'first_login_at', 'created_at')
    
    fieldsets = (
        ('基本信息', {
            'fields': ('user',)
        }),
        ('登录状态', {
            'fields': ('has_changed_password', 'first_login_at'),
            'description': '追踪用户首次登录和密码修改情况'
        }),
        ('系统信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_user_display(self, obj):
        """显示用户信息"""
        user = obj.user
        full_name = user.get_full_name()
        if full_name:
            return f'{full_name} ({user.username})'
        return user.username
    get_user_display.short_description = '用户'

    def get_groups_display(self, obj):
        """显示用户所属组"""
        groups = obj.user.groups.all()
        if obj.user.is_superuser:
            return mark_safe('<span style="color: #f57c00; font-weight: bold;">👑 超级管理员</span>')
        if not groups:
            return '---'
        return ', '.join([g.name for g in groups])
    get_groups_display.short_description = '用户组'

    def status_indicator(self, obj):
        """状态指示器"""
        if obj.has_changed_password:
            return mark_safe('<span style="color: green;">✓ 已修改密码</span>')
        else:
            return mark_safe('<span style="color: orange;">⚠️ 未修改密码</span>')
    status_indicator.short_description = '密码状态'

    def has_add_permission(self, request):
        """防止直接添加UserProfile，应通过User创建"""
        return False


class UserManagementAuditAdmin(admin.ModelAdmin):
    """用户管理审计日志 - 记录所有用户和用户组的管理操作"""
    list_display = ('created_at', 'operator', 'get_action_display_colored', 'get_target', 'details_preview')
    list_filter = ('action', 'created_at', 'operator')
    search_fields = ('operator__username', 'target_user__username', 'target_group__name', 'details')
    readonly_fields = ('operator', 'action', 'target_user', 'target_group', 'details', 'created_at')
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('操作信息', {
            'fields': ('operator', 'action', 'created_at')
        }),
        ('操作目标', {
            'fields': ('target_user', 'target_group')
        }),
        ('操作详情', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
    )

    def get_action_display_colored(self, obj):
        """带颜色的操作类型显示"""
        colors = {
            'add_user': '#28a745',
            'change_user': '#007bff',
            'delete_user': '#dc3545',
            'add_group': '#28a745',
            'change_group': '#007bff',
            'delete_group': '#dc3545',
            'add_to_group': '#17a2b8',
            'remove_from_group': '#ffc107',
        }
        color = colors.get(obj.action, '#6c757d')
        return mark_safe(f'<span style="color: {color}; font-weight: bold;">{obj.get_action_display()}</span>')
    get_action_display_colored.short_description = '操作类型'

    def get_target(self, obj):
        """显示操作的目标"""
        if obj.target_user:
            icon = '👤'
            name = obj.target_user.get_full_name() or obj.target_user.username
            return mark_safe(f'{icon} {name} <small>({obj.target_user.username})</small>')
        elif obj.target_group:
            return mark_safe(f'👥 {obj.target_group.name}')
        return '---'
    get_target.short_description = '操作目标'

    def details_preview(self, obj):
        """操作详情预览"""
        if obj.details:
            preview = obj.details[:50] + ('...' if len(obj.details) > 50 else '')
            return preview
        return '---'
    details_preview.short_description = '详情预览'

    def has_add_permission(self, request):
        """防止手动添加审计记录"""
        return False

    def has_change_permission(self, request, obj=None):
        """防止修改审计记录"""
        return False

    def has_delete_permission(self, request, obj=None):
        """只有超级管理员可以删除审计记录"""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        """只有超级管理员和管理员可以查看审计日志"""
        return request.user.is_superuser or request.user.groups.filter(name='管理员').exists()


# 注册或重新注册 User 和 Group
if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)

# 注册 UserProfile
if not admin.site.is_registered(UserProfile):
    admin.site.register(UserProfile, UserProfileAdmin)

# 注册 UserManagementAudit
if not admin.site.is_registered(UserManagementAudit):
    admin.site.register(UserManagementAudit, UserManagementAuditAdmin)



