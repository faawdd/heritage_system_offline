from django.contrib import admin
from .models import HeritageSite, InspectionRecord, ProjectAudit, UserProfile
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.utils.html import format_html, mark_safe
from django.contrib import messages
import csv
from django.http import HttpResponse
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
import os
import zipfile
import io
from .utils import generate_word_log, generate_project_docx_response
import json
from django.shortcuts import render
import re




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
    list_display = ('sip_code', 'name', 'category', 'level', 'manager')
    list_filter = ('category', 'level', KanerjingFilter)
    search_fields = ('name', 'sip_code', 'address')
    list_editable = ('manager',) # 记得这个逗号

    def get_queryset(self, request):
        """获取查询集"""
        qs = super().get_queryset(request)
        return qs
    
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
        """看护员只能看自己的巡查记录"""
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.is_staff and request.user.groups.filter(name='管理员').exists():
            return qs
        # 普通看护员只能看自己的记录
        return qs.filter(inspector=request.user)

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

@admin.register(ProjectAudit)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_name', 'project_unit', 'workflow_status_display', 'alert_status', 'received_date')
    list_filter = ('workflow_status', 'is_in_protection_zone', 'is_in_control_zone', 'received_date')
    search_fields = ('project_name', 'project_unit', 'archive_number')
    readonly_fields = ('is_in_protection_zone', 'is_in_control_zone', 'received_date')
    date_hierarchy = 'received_date'
    
    fieldsets = (
        ('基本信息', {
            'fields': (
                'project_name',
                'project_unit',
                'construction_content',
                'project_scale',
                'project_coordinates',
                'related_site',
                'project_lon',
                'project_lat',
                'workflow_status',
            )
        }),
        ('阶段1：项目方提交查询函', {
            'fields': ('inquiry_letter', 'ovital_kml_file', 'received_date'),
            'classes': ('collapse',)
        }),
        ('阶段2：奥维查询', {
            'fields': ('ovital_query_record', 'ovital_query_date'),
            'classes': ('collapse',)
        }),
        ('阶段3：现场勘察', {
            'fields': ('site_survey_record', 'site_survey_photos', 'site_survey_date', 
                      'is_in_protection_zone', 'is_in_control_zone', 'survey_conclusion'),
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
            'fields': ('archive_number', 'archived_date'),
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

    def export_upward_request_docx(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '请只选择 1 条项目记录进行上行文生成。', level=messages.WARNING)
            return

        project = queryset.first()
        try:
            return generate_project_docx_response(project)
        except FileNotFoundError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        except Exception as exc:
            self.message_user(request, f'生成上行文失败：{exc}', level=messages.ERROR)

    export_upward_request_docx.short_description = '生成上行文 Word（docxtpl）'
    actions = ['export_upward_request_docx']



# 修改后台左上角显示的文字
admin.site.site_header = '鄯善县文物数字化管理平台'

# 修改浏览器标签页显示的文字
admin.site.site_title = '基层文物管理系统'

# 修改后台首页的欢迎提示文字
admin.site.index_title = '欢迎使用文物安全巡查与项目管理系统'


# ============ 用户和组管理 ============

class CustomUserAdmin(BaseUserAdmin):
    """优化的用户管理界面"""
    list_display = ('username', 'get_full_name', 'email', 'is_staff', 'is_active', 'get_groups', 'last_login')
    list_filter = ('is_staff', 'is_active', 'groups', 'date_joined')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {
            'fields': ('first_name', 'last_name', 'email'),
            'classes': ('wide',)
        }),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups'),
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
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    readonly_fields = ('last_login', 'date_joined')

    def get_full_name(self, obj):
        """显示全名"""
        return obj.get_full_name() or '---'
    get_full_name.short_description = '姓名'

    def get_groups(self, obj):
        """显示用户所属组"""
        return ', '.join([g.name for g in obj.groups.all()]) or '---'
    get_groups.short_description = '用户组'


class CustomGroupAdmin(BaseGroupAdmin):
    """优化的用户组管理界面"""
    list_display = ('name', 'get_permission_count', 'get_members_count')
    filter_horizontal = ('permissions',)

    def get_permission_count(self, obj):
        """权限数量"""
        return obj.permissions.count()
    get_permission_count.short_description = '权限数'

    def get_members_count(self, obj):
        """组成员数量"""
        return obj.user_set.count()
    get_members_count.short_description = '成员数'


class UserProfileAdmin(admin.ModelAdmin):
    """用户密码修改记录管理"""
    list_display = ('get_username', 'user', 'has_changed_password', 'first_login_at', 'created_at')
    list_filter = ('has_changed_password', 'created_at', 'first_login_at')
    search_fields = ('user__username', 'user__first_name')
    readonly_fields = ('user', 'first_login_at', 'created_at')
    
    def get_username(self, obj):
        """显示用户名"""
        return obj.user.get_full_name() or obj.user.username
    get_username.short_description = '看护员'
    
    fieldsets = (
        ('用户信息', {
            'fields': ('user',)
        }),
        ('密码修改状态', {
            'fields': ('has_changed_password', 'first_login_at'),
            'description': '追踪用户首次登录和密码修改情况'
        }),
        ('记录信息', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


# 注册或重新注册 User 和 Group
if not admin.site.is_registered(User):
    admin.site.register(User, CustomUserAdmin)
else:
    admin.site.unregister(User)
    admin.site.register(User, CustomUserAdmin)

if not admin.site.is_registered(Group):
    admin.site.register(Group, CustomGroupAdmin)
else:
    admin.site.unregister(Group)
    admin.site.register(Group, CustomGroupAdmin)

# 注册 UserProfile
if not admin.site.is_registered(UserProfile):
    admin.site.register(UserProfile, UserProfileAdmin)
else:
    admin.site.unregister(UserProfile)
    admin.site.register(UserProfile, UserProfileAdmin)



