from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
import json

# 1. 不可移动文物基础表（结合四普字段）
class HeritageSite(models.Model):
    CATEGORY_CHOICES = [
        ('GYZ', '古文化遗址'), ('GMZ', '古墓葬'), ('GJZ', '古建筑'),
        ('SKT', '石窟寺及石刻'), ('JDJW', '近现代重要史迹及代表性建筑'),
        ('KRJ', '坎儿井'), ('QT', '其他')
    ]
    LEVEL_CHOICES = [('GB', '全国重点文物保护单位'), ('SB', '自治区级文物保护单位'), ('XB', '县级文物保护单位'), ('DS', '尚未定级的不可移动文物')]
    KANERJING_CATEGORY_CODE = 'KRJ'

    name = models.CharField("文物名称", max_length=200)
    sip_code = models.CharField("四普编号", max_length=50, unique=True)
    category = models.CharField("类别", max_length=10, choices=CATEGORY_CHOICES)
    level = models.CharField("保护级别", max_length=10, choices=LEVEL_CHOICES)
    address = models.CharField("详细地址", max_length=500)
    
    # 空间坐标
    longitude = models.FloatField("经度")
    latitude = models.FloatField("纬度")
    
    # 四普描述
    description = models.TextField("现状描述", help_text="对比三普的变化情况")
    manager = models.CharField("管理责任单位/人", max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.get_level_display()}] {self.name}"

    @classmethod
    def kanerjing_query(cls):
        return Q(name__icontains='坎儿井') | Q(category=cls.KANERJING_CATEGORY_CODE)

    @classmethod
    def filter_kanerjing(cls, queryset=None):
        base_queryset = queryset if queryset is not None else cls.objects.all()
        return base_queryset.filter(cls.kanerjing_query())

    @classmethod
    def exclude_kanerjing(cls, queryset=None):
        base_queryset = queryset if queryset is not None else cls.objects.all()
        return base_queryset.exclude(cls.kanerjing_query())

    class Meta:
        verbose_name = "不可移动文物档案"
        verbose_name_plural = verbose_name

    # 新增：两线坐标数据 (存储为 JSON 字符串，例如: "[[116.1, 39.1], [116.2, 39.1], ...]")
    protection_zone = models.TextField("保护范围坐标集合", null=True,blank=True, help_text="请输入经纬度序列JSON")
    control_zone = models.TextField("建控地带坐标集合", null=True, blank=True)

    @staticmethod
    def _point_in_polygon(lon, lat, polygon_points):
        """射线法判断点是否在多边形内（含边界近似）"""
        if not polygon_points or len(polygon_points) < 3:
            return False

        inside = False
        point_count = len(polygon_points)

        for index in range(point_count):
            x1, y1 = polygon_points[index]
            x2, y2 = polygon_points[(index + 1) % point_count]

            if ((y1 > lat) != (y2 > lat)):
                cross_x = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
                if lon <= cross_x:
                    inside = not inside

        return inside

    @staticmethod
    def _load_polygon_points(zone_text):
        """将 JSON 坐标解析为 [(lon, lat), ...]"""
        if not zone_text:
            return []

        try:
            parsed = json.loads(zone_text)
        except Exception:
            return []

        points = []
        for item in parsed:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    points.append((float(item[0]), float(item[1])))
                except (TypeError, ValueError):
                    continue
            elif isinstance(item, dict):
                lon = item.get('lon', item.get('longitude'))
                lat = item.get('lat', item.get('latitude'))
                try:
                    points.append((float(lon), float(lat)))
                except (TypeError, ValueError):
                    continue

        return points

    def is_inside_zones(self, lon, lat):
        """判断给定的点是否落入两线"""
        results = {"in_protection": False, "in_control": False}
        try:
            point_lon = float(lon)
            point_lat = float(lat)
        except (TypeError, ValueError):
            return results
        
        # 检查保护范围
        if self.protection_zone:
            protection_points = self._load_polygon_points(self.protection_zone)
            if self._point_in_polygon(point_lon, point_lat, protection_points):
                results["in_protection"] = True
        
        # 检查建控地带
        if self.control_zone:
            control_points = self._load_polygon_points(self.control_zone)
            if self._point_in_polygon(point_lon, point_lat, control_points):
                results["in_control"] = True
                
        return results

# 2. 基层巡查登记表
class InspectionRecord(models.Model):
    site = models.ForeignKey(HeritageSite, on_delete=models.CASCADE, verbose_name="巡查对象")
    inspector = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="巡查员")
    inspect_time = models.DateTimeField("巡查时间", auto_now_add=True)
    
    is_normal = models.BooleanField("是否正常", default=True)
    issue_details = models.TextField("发现问题", blank=True, null=True)
    photo = models.ImageField("现场拍照", upload_to='inspections/%Y/%m/', blank=True)
    
    # 巡查时的位置信息（用于水印和数据记录）
    latitude = models.FloatField("巡查纬度", null=True, blank=True, help_text="巡查时的GPS纬度")
    longitude = models.FloatField("巡查经度", null=True, blank=True, help_text="巡查时的GPS经度")

    class Meta:
        verbose_name = "巡查登记存档"
        verbose_name_plural = verbose_name
        ordering = ['-inspect_time']  # 按时间倒序排列

# 3. 项目管理表（原工程建设核查）
class ProjectAudit(models.Model):
    WORKFLOW_STATUS_CHOICES = [
        ('received', '已接收查询函'),
        ('ovital_checked', '奥维查询完成'),
        ('site_surveyed', '现场勘察完成'),
        ('application_submitted', '已上报市文物局'),
        ('bureau_approved', '市局审批完成'),
        ('replied_to_project', '已回函项目方'),
        ('archived', '归档完成'),
    ]
    
    # 基本信息
    project_name = models.CharField("建设项目名称", max_length=200)
    project_unit = models.CharField("项目单位", max_length=200, blank=True)
    construction_content = models.TextField("工程建设内容与地址", default='')
    project_scale = models.CharField("项目建设的规模", max_length=500, default='')
    project_coordinates = models.TextField("项目选址的经纬度坐标", default='')
    related_site = models.ForeignKey(HeritageSite, on_delete=models.CASCADE, verbose_name="涉及文物", null=True, blank=True)
    
    # 拟建项目坐标
    project_lon = models.FloatField("项目经度", null=True, blank=True)
    project_lat = models.FloatField("项目纬度", null=True, blank=True)

    # 工作流状态
    workflow_status = models.CharField("工作流状态", max_length=30, choices=WORKFLOW_STATUS_CHOICES, default='received')
    
    # 阶段1：项目方提交查询函
    inquiry_letter = models.FileField("项目方查询函", upload_to='projects/inquiry_letters/', blank=True, help_text="支持PDF或DOCX格式")
    ovital_kml_file = models.FileField("奥维KML文件", upload_to='projects/kml_files/', blank=True)
    received_date = models.DateTimeField("接收日期", null=True, blank=True)
    
    # 阶段2：奥维查询
    ovital_query_record = models.TextField("奥维查询记录", blank=True, help_text="记录奥维地图查询情况")
    ovital_query_date = models.DateTimeField("奥维查询日期", null=True, blank=True)
    
    # 阶段3：现场勘察
    site_survey_record = models.TextField("现场勘察记录", blank=True, help_text="记录现场勘察情况")
    site_survey_photos = models.FileField("现场勘察照片", upload_to='projects/survey_photos/', blank=True, help_text="可上传照片压缩包")
    site_survey_date = models.DateTimeField("现场勘察日期", null=True, blank=True)
    
    # 两线判断结果
    is_in_protection_zone = models.BooleanField("是否在保护范围内", default=False)
    is_in_control_zone = models.BooleanField("是否在建控地带内", default=False)
    survey_conclusion = models.TextField("勘察结论", blank=True, help_text="项目是否涉及文物的最终结论")
    
    # 阶段4：上报市文物局
    application_report = models.FileField("上报申请报告", upload_to='projects/applications/', blank=True)
    application_date = models.DateTimeField("上报日期", null=True, blank=True)
    
    # 阶段5：市文物局审批
    bureau_approval_reply = models.FileField("市文物局复函", upload_to='projects/bureau_replies/', blank=True)
    bureau_approval_date = models.DateTimeField("市局批复日期", null=True, blank=True)
    bureau_opinion = models.TextField("市局审批意见", blank=True)
    
    # 阶段6：回函项目方
    project_reply_letter = models.FileField("回函项目方", upload_to='projects/project_replies/', blank=True)
    project_reply_date = models.DateTimeField("回函日期", null=True, blank=True)
    
    # 归档信息
    archive_number = models.CharField("归档编号", max_length=100, blank=True)
    archived_date = models.DateTimeField("归档日期", null=True, blank=True)
    
    # 备注
    remarks = models.TextField("备注", blank=True)
    
    # 旧字段（保留兼容）
    audit_opinion = models.TextField("核查意见", blank=True)
    status = models.CharField("审核状态", max_length=20, choices=[('Pending', '待审'), ('Pass', '通过'), ('Reject', '驳回')], default='Pending')
    file_archive = models.FileField("附件存档", upload_to='projects/docs/', blank=True)
    
    def __str__(self):
        return f"{self.project_name} - {self.get_workflow_status_display()}"
    
    def save(self, *args, **kwargs):
        # 首次创建时自动设置接收日期
        if not self.pk and not self.received_date:
            from django.utils import timezone
            self.received_date = timezone.now()
        
        # 如果有相关文物和坐标，自动调用文物的判断逻辑
        if self.related_site and self.project_lon and self.project_lat:
            check_res = self.related_site.is_inside_zones(self.project_lon, self.project_lat)
            self.is_in_protection_zone = check_res["in_protection"]
            self.is_in_control_zone = check_res["in_control"]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "项目管理"
        verbose_name_plural = verbose_name
        ordering = ['-received_date']


class Coordinate(models.Model):
    """输变电项目杆塔坐标点"""
    CHECK_STATUS_CHOICES = [
        ('pending', '待核查'),
        ('checked', '已核查'),
    ]

    project = models.ForeignKey(
        ProjectAudit,
        on_delete=models.CASCADE,
        related_name='coordinates',
        verbose_name='所属工程项目'
    )
    tower_no = models.CharField('杆塔号', max_length=50)
    cgcs2000_x = models.DecimalField('CGCS2000 X', max_digits=16, decimal_places=3, null=True, blank=True)
    cgcs2000_y = models.DecimalField('CGCS2000 Y', max_digits=16, decimal_places=3, null=True, blank=True)
    longitude = models.FloatField('经度', null=True, blank=True)
    latitude = models.FloatField('纬度', null=True, blank=True)
    is_on_boundary = models.BooleanField('是否位于保护区边界', default=False)
    check_status = models.CharField('核查状态', max_length=20, choices=CHECK_STATUS_CHOICES, default='pending')
    remark = models.CharField('位置说明', max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.project_name}-{self.tower_no}"

    class Meta:
        verbose_name = '杆塔坐标'
        verbose_name_plural = verbose_name
        ordering = ['project_id', 'tower_no']


# 4. 用户配置文件（追踪首次登录）
class UserProfile(models.Model):
    """追踪用户首次登录，提示修改密码"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    has_changed_password = models.BooleanField("是否已修改密码", default=False)
    first_login_at = models.DateTimeField("首次登录时间", null=True, blank=True)
    contact_info = models.CharField("联系方式", max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - 已改密: {self.has_changed_password}"
    
    class Meta:
        verbose_name = "用户密码修改记录"
        verbose_name_plural = verbose_name


# 5. 用户管理审计日志
class UserManagementAudit(models.Model):
    """记录用户和用户组的管理操作"""
    ACTION_CHOICES = [
        ('add_user', '创建用户'),
        ('change_user', '修改用户'),
        ('delete_user', '删除用户'),
        ('add_group', '创建用户组'),
        ('change_group', '修改用户组'),
        ('delete_group', '删除用户组'),
        ('add_to_group', '添加用户到组'),
        ('remove_from_group', '从组移除用户'),
    ]
    
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='management_actions', verbose_name='操作员')
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='management_logs', verbose_name='目标用户')
    target_group = models.ForeignKey('auth.Group', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='目标用户组')
    details = models.TextField('操作详情', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)
    
    def __str__(self):
        target = self.target_user or self.target_group
        return f"{self.operator} - {self.get_action_display()} - {target}"
    
    class Meta:
        verbose_name = "用户管理审计日志"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['operator']),
            models.Index(fields=['action']),
        ]


class KmlUploadRecord(models.Model):
    """KML/KMZ 文件管理与冲突分析记录"""
    title = models.CharField('文件标题', max_length=255)
    source_file = models.FileField('KML文件', upload_to='kml_uploads/%Y/%m/')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kml_upload_records',
        verbose_name='上传人'
    )
    threshold_m = models.PositiveIntegerField('冲突阈值(米)', default=50)
    feature_count = models.PositiveIntegerField('要素数量', default=0)
    conflict_count = models.PositiveIntegerField('冲突数量', default=0)
    report_json = models.TextField('冲突报告JSON', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.conflict_count}处冲突)"

    class Meta:
        verbose_name = 'KML文件管理'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
