from django.db import models, IntegrityError, transaction
from django.db.models import Q
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid
import json
import re

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

    # 新增：两线坐标数据（存储为 JSON 字符串，格式统一为“环列表”：
    # [[[lon,lat], [lon,lat], ...], [[lon,lat], ...], ...]，支持一个文物点存在多个分离区块。
    protection_zone = models.TextField("保护范围坐标集合", null=True, blank=True, help_text="JSON 环列表：[[[lon,lat],...],...]")
    control_zone = models.TextField("建控地带坐标集合", null=True, blank=True, help_text="JSON 环列表：[[[lon,lat],...],...]")
    # 从四普系统“文物矢量图”导入的本体边界范围，格式同上，用于KML叠加检查替代单点坐标。
    body_boundary = models.TextField("本体边界范围坐标集合", null=True, blank=True, help_text="JSON 环列表：[[[lon,lat],...],...]")

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
    def _load_polygon_rings(zone_text):
        """将 JSON 环列表解析为 [[(lon, lat), ...], ...]，兼容旧版单环（扁平坐标数组）格式。"""
        if not zone_text:
            return []

        try:
            parsed = json.loads(zone_text)
        except Exception:
            return []

        if not isinstance(parsed, list) or not parsed:
            return []

        def _parse_ring(raw_ring):
            ring = []
            for item in raw_ring:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    try:
                        ring.append((float(item[0]), float(item[1])))
                    except (TypeError, ValueError):
                        continue
                elif isinstance(item, dict):
                    lon = item.get('lon', item.get('longitude'))
                    lat = item.get('lat', item.get('latitude'))
                    try:
                        ring.append((float(lon), float(lat)))
                    except (TypeError, ValueError):
                        continue
            return ring

        first_item = parsed[0]
        # 旧版扁平单环格式：[[lon,lat], [lon,lat], ...]
        if isinstance(first_item, (list, tuple)) and len(first_item) >= 2 and isinstance(first_item[0], (int, float, str)):
            ring = _parse_ring(parsed)
            return [ring] if ring else []

        # 新版环列表格式：[[[lon,lat],...], [[lon,lat],...], ...]
        rings = []
        for raw_ring in parsed:
            if not isinstance(raw_ring, list):
                continue
            ring = _parse_ring(raw_ring)
            if ring:
                rings.append(ring)
        return rings

    @classmethod
    def _load_polygon_points(cls, zone_text):
        """兼容旧调用：仅返回第一个环的坐标点。"""
        rings = cls._load_polygon_rings(zone_text)
        return rings[0] if rings else []

    def is_inside_zones(self, lon, lat):
        """判断给定的点是否落入两线（任一分区块命中即算落入）"""
        results = {"in_protection": False, "in_control": False}
        try:
            point_lon = float(lon)
            point_lat = float(lat)
        except (TypeError, ValueError):
            return results
        
        # 检查保护范围
        if self.protection_zone:
            for ring in self._load_polygon_rings(self.protection_zone):
                if self._point_in_polygon(point_lon, point_lat, ring):
                    results["in_protection"] = True
                    break
        
        # 检查建控地带
        if self.control_zone:
            for ring in self._load_polygon_rings(self.control_zone):
                if self._point_in_polygon(point_lon, point_lat, ring):
                    results["in_control"] = True
                    break
                
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


class LandUseProjectApproval(models.Model):
    """基层文物管理-用地项目审批与文档登记归档主表。"""

    STATUS_RECEIVED = '10_已收文'
    STATUS_PRELIM_SAFE = '20_初审安全'
    STATUS_CHECK_OVERLAP = '21_CHECK_OVERLAP'
    STATUS_FIELD_DONE = '30_现场勘查完成'
    STATUS_CITY_REVIEWING = '40_市局审批中'
    STATUS_ARCHAEOLOGY = '45_考古流转中'
    STATUS_REPLY_RECEIVED = '50_批复已收到'
    STATUS_ARCHIVED = '60_已结案归档'

    STATUS_CHOICES = [
        (STATUS_RECEIVED, '10_已收文'),
        (STATUS_PRELIM_SAFE, '20_初审安全'),
        (STATUS_CHECK_OVERLAP, '21_初审涉及'),
        (STATUS_FIELD_DONE, '30_现场勘查完成'),
        (STATUS_CITY_REVIEWING, '40_市局审批中'),
        (STATUS_ARCHAEOLOGY, '45_考古流转中'),
        (STATUS_REPLY_RECEIVED, '50_批复已收到'),
        (STATUS_ARCHIVED, '60_已结案归档'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # 收文登记
    project_name = models.CharField('用地项目名称', max_length=255)
    company_name = models.CharField('企业单位名称', max_length=255)
    incoming_doc_date = models.DateField('企业来函日期', default=timezone.localdate)
    receive_date = models.DateField('收文日期', default=timezone.localdate)
    kml_file_path = models.CharField('原始KML文件路径', max_length=500, blank=True, default='')
    misc_zip_path = models.CharField('杂项ZIP文件路径', max_length=500, blank=True, default='')

    # 空间核验结果
    is_overlap_artifact = models.BooleanField('是否涉及文物', default=False)
    overlapped_relics_info = models.JSONField('涉事文物信息', default=list, blank=True)
    status = models.CharField('项目状态', max_length=32, choices=STATUS_CHOICES, default=STATUS_RECEIVED)

    # 流程A字段
    field_check_date = models.DateField('现场勘查日期', null=True, blank=True)
    shanshan_request_num = models.CharField(
        '县局请示文号',
        max_length=100,
        blank=True,
        default='',
        validators=[
            RegexValidator(
                regex=r'^鄯文旅字-\d{4}-\d+号$',
                message='县局请示文号格式应为：鄯文旅字-2026-xx号',
            )
        ],
    )
    city_reply_num = models.CharField('市局复函文号', max_length=120, blank=True, default='')

    # 流程B字段
    archaeology_request_num = models.CharField('考古请示文号', max_length=120, blank=True, default='')
    archaeology_report_path = models.CharField('考古调查报告路径', max_length=500, blank=True, default='')
    region_approval_num = models.CharField('自治区文物局批复文号', max_length=120, blank=True, default='')
    city_final_reply_num = models.CharField('市文物局最终复函号', max_length=120, blank=True, default='')

    # 坎儿井保护加固与水利部门意见（涉及坎儿井时按流程要求编制方案并征求意见）
    involves_kanerjing = models.BooleanField('是否涉及坎儿井', default=False)
    kanerjing_protection_plan_path = models.CharField('坎儿井保护加固方案路径', max_length=500, blank=True, default='')
    water_department_opinion = models.TextField('水利部门意见', blank=True, default='')

    # 逐级报审：市级之外，依法需要时可报自治区/国务院文物行政部门
    requires_state_council_approval = models.BooleanField('是否需报国务院文物行政部门', default=False)
    state_council_approval_num = models.CharField('国务院文物行政部门批复文号', max_length=120, blank=True, default='')

    # 办结归档
    final_reply_to_company = models.CharField('给企业最终复函号', max_length=120, blank=True, default='')
    protection_measures_note = models.TextField('保护措施落实情况说明', blank=True, default='')
    protection_measures_confirmed = models.BooleanField('保护措施落实核实', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return f"{self.project_name} - {self.get_status_display()}"

    @classmethod
    def suggest_next_shanshan_num(cls, year=None):
        """按年度扫描历史文号，返回推荐的下一个编号文本。"""
        target_year = int(year or timezone.localdate().year)
        pattern = re.compile(rf'^鄯文旅字-{target_year}-(\d+)号$')
        max_no = 0
        for value in cls.objects.exclude(shanshan_request_num='').values_list('shanshan_request_num', flat=True):
            matched = pattern.match((value or '').strip())
            if not matched:
                continue
            max_no = max(max_no, int(matched.group(1)))
        return f'鄯文旅字-{target_year}-{max_no + 1}号'

    class Meta:
        verbose_name = '用地项目审批归档'
        verbose_name_plural = verbose_name
        ordering = ['-receive_date', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['receive_date']),
            models.Index(fields=['company_name']),
        ]


class LandUseProjectFieldPhoto(models.Model):
    """流程A现场照片多附件表。"""

    project = models.ForeignKey(
        LandUseProjectApproval,
        on_delete=models.CASCADE,
        related_name='field_photos',
        verbose_name='所属项目',
    )
    photo_path = models.CharField('现场照片路径', max_length=500)
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)
    note = models.CharField('备注', max_length=200, blank=True, default='')

    def __str__(self):
        return f"{self.project.project_name}-现场照片{self.id}"

    class Meta:
        verbose_name = '用地项目现场照片'
        verbose_name_plural = verbose_name
        ordering = ['-uploaded_at']


class LandUseProjectOperationLog(models.Model):
    """用地项目流程操作日志。"""

    project = models.ForeignKey(
        LandUseProjectApproval,
        on_delete=models.CASCADE,
        related_name='operation_logs',
        verbose_name='所属项目',
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='land_project_operation_logs',
        verbose_name='操作人',
    )
    action = models.CharField('动作编码', max_length=50)
    action_label = models.CharField('动作名称', max_length=120, blank=True, default='')
    payload = models.JSONField('动作参数', default=dict, blank=True)
    status_before = models.CharField('操作前状态', max_length=32, blank=True, default='')
    status_after = models.CharField('操作后状态', max_length=32, blank=True, default='')
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    def __str__(self):
        return f"{self.project.project_name}-{self.action}@{self.created_at:%Y-%m-%d %H:%M}"

    class Meta:
        verbose_name = '用地项目流程日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['action']),
        ]


class SipuImportJob(models.Model):
    """四普系统文物矢量图边界导入任务：记录后台线程的分页导入进度，供前端轮询展示进度条。"""

    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_RUNNING, '进行中'),
        (STATUS_SUCCESS, '已完成'),
        (STATUS_FAILED, '失败'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    total = models.IntegerField('总数', default=0)
    processed = models.IntegerField('已处理数', default=0)
    matched = models.IntegerField('成功写入数', default=0)
    unmatched_count = models.IntegerField('未匹配数', default=0)
    no_geometry_count = models.IntegerField('无矢量数据数', default=0)
    unmatched_items = models.JSONField('未匹配明细', default=list, blank=True)
    no_geometry_items = models.JSONField('无矢量数据明细', default=list, blank=True)
    error_message = models.TextField('错误信息', blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sipu_import_jobs', verbose_name='发起人',
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    def __str__(self):
        return f"SipuImportJob({self.id})-{self.status}"

    class Meta:
        verbose_name = '四普边界导入任务'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


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


# ============================================================
# 第四次全国文物普查 —— 不可移动文物登记表（ImmovableHeritage）
# ============================================================

class ImmovableHeritage(models.Model):
    """
    不可移动文物点登记模型，字段严格对应
    《第四次全国文物普查不可移动文物登记表》核心指标。

    默认使用 DecimalField 存储经纬度（高精度）；
    如已安装 GeoDjango + PostGIS，可将注释中的 PointField 方案替换默认字段。
    """

    # ------------------------------------------------------------------
    # 一、文物类别（四普六大类 + 子类型）
    # ------------------------------------------------------------------
    CATEGORY_CHOICES = [
        ('GWZ',  '古文化遗址'),
        ('GMZ',  '古墓葬'),
        ('GJZ',  '古建筑'),
        ('SKT',  '石窟寺及石刻'),
        ('JDJW', '近现代重要史迹及代表性建筑'),
        ('QT',   '其他'),
    ]

    # 四普文物类别子类型（简化，可按实际扩充）
    HERITAGE_TYPE_CHOICES = [
        # 古文化遗址
        ('聚落址',     '聚落址'),
        ('城址',       '城址'),
        ('宫殿衙署址', '宫殿衙署址'),
        ('宗教祭祀址', '宗教祭祀址'),
        ('烽燧',       '烽燧'),
        ('长城',       '长城'),
        ('驿道',       '驿道'),
        ('水工设施',   '水工设施'),
        ('窑址',       '窑址'),
        ('矿冶遗址',   '矿冶遗址'),
        ('手工业作坊址', '手工业作坊址'),
        ('岩画',       '岩画'),
        ('古战场',     '古战场'),
        ('其他古遗址', '其他古遗址'),
        # 古墓葬
        ('帝王陵寝',   '帝王陵寝'),
        ('贵族墓葬',   '贵族墓葬'),
        ('普通墓葬',   '普通墓葬'),
        ('墓地/墓群',  '墓地/墓群'),
        # 古建筑
        ('城垣城楼',   '城垣城楼'),
        ('宫殿府邸',   '宫殿府邸'),
        ('坛庙祠堂',   '坛庙祠堂'),
        ('衙署官府',   '衙署官府'),
        ('学堂书院',   '学堂书院'),
        ('驿站会馆',   '驿站会馆'),
        ('民居建筑',   '民居建筑'),
        ('宗教建筑',   '宗教建筑'),
        ('楼阁亭塔',   '楼阁亭塔'),
        ('桥涵码头',   '桥涵码头'),
        ('堤坝渠堰',   '堤坝渠堰'),
        ('池苑园林',   '池苑园林'),
        ('其他古建筑', '其他古建筑'),
        # 石窟寺及石刻
        ('石窟寺',     '石窟寺'),
        ('摩崖石刻',   '摩崖石刻'),
        ('碑刻',       '碑刻'),
        ('石雕',       '石雕'),
        ('岩刻图案',   '岩刻图案'),
        # 近现代重要史迹及代表性建筑
        ('重要历史事件及人物活动纪念地', '重要历史事件及人物活动纪念地'),
        ('重要历史事件发生地旧址',       '重要历史事件发生地旧址'),
        ('名人故居旧居',                 '名人故居旧居'),
        ('工业遗产',                     '工业遗产'),
        ('金融商贸建筑',                 '金融商贸建筑'),
        ('文化教育建筑',                 '文化教育建筑'),
        ('医疗卫生建筑',                 '医疗卫生建筑'),
        ('交通道路设施',                 '交通道路设施'),
        ('水利设施',                     '水利设施'),
        ('军事设施',                     '军事设施'),
        ('典型风格建筑',                 '典型风格建筑'),
        ('其他近现代重要史迹', '其他近现代重要史迹'),
        # 其他
        ('其他', '其他'),
    ]

    # 保存现状（四普标准五级）
    PRESERVATION_STATUS_CHOICES = [
        ('好',   '好'),
        ('较好', '较好'),
        ('一般', '一般'),
        ('较差', '较差'),
        ('差',   '差'),
    ]

    # 保护级别
    PROTECTION_LEVEL_CHOICES = [
        ('GB', '全国重点文物保护单位'),
        ('SB', '省（自治区、直辖市）级文物保护单位'),
        ('XB', '市（县）级文物保护单位'),
        ('DS', '尚未定级的不可移动文物'),
    ]

    # 权属
    OWNERSHIP_CHOICES = [
        ('state',      '国有'),
        ('collective', '集体'),
        ('private',    '私人'),
        ('other',      '其他'),
    ]

    # 坐标系
    COORDINATE_SYSTEM_CHOICES = [
        ('CGCS2000', '2000国家大地坐标系（CGCS2000）'),
        ('WGS84',    'WGS84坐标系'),
        ('BJ54',     '北京54坐标系'),
        ('XA80',     '西安80坐标系'),
    ]

    # ------------------------------------------------------------------
    # 二、基础信息
    # ------------------------------------------------------------------
    survey_code = models.CharField(
        verbose_name='采集编号',
        max_length=50,
        unique=True,
        blank=True,
        default='',
        help_text='系统自动生成，格式：SS-CJ-YYYY-NNNN（如 SS-CJ-2026-0001）',
    )
    previous_survey_code = models.CharField(
        verbose_name='原三普编号',
        max_length=50,
        blank=True,
        default='',
        help_text='第三次全国文物普查登记编号，新发现文物可留空',
    )
    name = models.CharField(
        verbose_name='文物名称',
        max_length=200,
        help_text='文物点标准名称，与登记表一致',
    )
    former_name = models.CharField(
        verbose_name='曾用名/别名',
        max_length=200,
        blank=True,
        default='',
        help_text='曾使用过的其他名称，多个名称用顿号分隔',
    )
    era = models.CharField(
        verbose_name='时代',
        max_length=100,
        help_text='文物所属历史时代，如"汉""唐宋""近现代"，可填年代范围',
    )
    category = models.CharField(
        verbose_name='文物类别',
        max_length=10,
        choices=CATEGORY_CHOICES,
        help_text='按第四次全国文物普查六大类划分',
    )
    heritage_type = models.CharField(
        verbose_name='文物类型',
        max_length=30,
        choices=HERITAGE_TYPE_CHOICES,
        blank=True,
        default='',
        help_text='类别下的具体类型，可参照四普分类体系选填',
    )

    # ------------------------------------------------------------------
    # 三、行政区划
    # ------------------------------------------------------------------
    province = models.CharField(
        verbose_name='省/自治区/直辖市',
        max_length=50,
        help_text='所在省级行政区名称',
    )
    city = models.CharField(
        verbose_name='市/州',
        max_length=50,
        blank=True,
        default='',
        help_text='所在地级市或自治州名称',
    )
    county = models.CharField(
        verbose_name='县/市/区',
        max_length=50,
        blank=True,
        default='',
        help_text='所在县级行政区名称',
    )
    township = models.CharField(
        verbose_name='乡镇/街道',
        max_length=100,
        blank=True,
        default='',
        help_text='所在乡镇或街道办事处名称',
    )
    village = models.CharField(
        verbose_name='村/社区',
        max_length=100,
        blank=True,
        default='',
        help_text='所在行政村或社区名称',
    )
    address = models.CharField(
        verbose_name='详细地址',
        max_length=500,
        help_text='精确到门牌号或自然地标的完整地址描述',
    )

    # ------------------------------------------------------------------
    # 四、地理空间信息（方案A：DecimalField，默认）
    # ------------------------------------------------------------------
    coordinate_system = models.CharField(
        verbose_name='坐标系',
        max_length=20,
        choices=COORDINATE_SYSTEM_CHOICES,
        default='CGCS2000',
        help_text='经纬度所采用的大地坐标系，优先使用CGCS2000',
    )
    longitude = models.DecimalField(
        verbose_name='经度（Longitude）',
        max_digits=11,
        decimal_places=8,
        help_text='WGS84/CGCS2000经度，范围 -180.00000000 ~ 180.00000000，精度保留8位小数',
    )
    latitude = models.DecimalField(
        verbose_name='纬度（Latitude）',
        max_digits=10,
        decimal_places=8,
        help_text='WGS84/CGCS2000纬度，范围 -90.00000000 ~ 90.00000000，精度保留8位小数',
    )
    altitude = models.DecimalField(
        verbose_name='海拔高程（米）',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='文物点主体所在位置的绝对海拔高度，单位：米',
    )
    coord_list = models.JSONField(
        verbose_name='区块2坐标点列表',
        default=list,
        blank=True,
        help_text='区块2采集的多点坐标信息，含类型、经纬高、说明与备注',
    )
    # 方案B（GeoDjango + PostGIS）：取消下方注释并注释掉上方 longitude/latitude/altitude 三个字段
    # 同时在 settings.py 的 INSTALLED_APPS 中加入 'django.contrib.gis'
    # from django.contrib.gis.db import models as gis_models
    # location = gis_models.PointField(
    #     verbose_name='空间坐标点',
    #     srid=4326,
    #     geography=True,
    #     null=True,
    #     blank=True,
    #     help_text='经纬度空间点，SRID=4326（WGS84），支持空间索引与GIS查询',
    # )

    area = models.DecimalField(
        verbose_name='占地面积（平方米）',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='文物本体及其附属范围的占地总面积，单位：平方米',
    )

    # ------------------------------------------------------------------
    # 五、保存状况与破坏因素
    # ------------------------------------------------------------------
    preservation_status = models.CharField(
        verbose_name='保存现状',
        max_length=4,
        choices=PRESERVATION_STATUS_CHOICES,
        help_text='文物整体保存状况评级（好 / 较好 / 一般 / 较差 / 差）',
    )
    damage_cause = models.TextField(
        verbose_name='破坏原因',
        blank=True,
        default='',
        help_text='造成文物破坏或损毁的主要原因，如自然风化、人为破坏、自然灾害等',
    )
    threat_factors = models.TextField(
        verbose_name='现存威胁因素',
        blank=True,
        default='',
        help_text='当前对文物存在威胁的自然或人为因素，可多条描述',
    )
    is_disappeared = models.BooleanField(
        verbose_name='是否已消失',
        default=False,
        help_text='文物是否已灭失或不复存在（四普新增核查项）',
    )
    disappear_reason = models.TextField(
        verbose_name='消失原因',
        blank=True,
        default='',
        help_text='文物灭失的具体原因，仅"是否已消失"为True时填写',
    )
    is_relocated = models.BooleanField(
        verbose_name='是否涉及迁移',
        default=False,
        help_text='文物点是否曾经或正在被整体迁移',
    )
    relocation_note = models.TextField(
        verbose_name='迁移情况说明',
        blank=True,
        default='',
        help_text='迁移的原因、时间及迁移前后地址，仅迁移文物填写',
    )

    # ------------------------------------------------------------------
    # 六、权属与管理
    # ------------------------------------------------------------------
    ownership = models.CharField(
        verbose_name='权属',
        max_length=20,
        choices=OWNERSHIP_CHOICES,
        help_text='文物所有权归属类型（国有 / 集体 / 私人 / 其他）',
    )
    ownership_detail = models.CharField(
        verbose_name='权属单位/人',
        max_length=200,
        blank=True,
        default='',
        help_text='具体的所有权单位或个人名称',
    )
    user_unit = models.CharField(
        verbose_name='使用单位/使用人',
        max_length=200,
        blank=True,
        default='',
        help_text='实际使用或占用该文物的单位或个人',
    )
    management_unit = models.CharField(
        verbose_name='管理单位',
        max_length=200,
        blank=True,
        default='',
        help_text='承担文物日常管理责任的单位，如文物所、博物馆、村委会等',
    )
    manager = models.CharField(
        verbose_name='管理责任人',
        max_length=100,
        blank=True,
        default='',
        help_text='具体负责文物日常管护的责任人姓名',
    )

    # ------------------------------------------------------------------
    # 七、保护级别与公布情况
    # ------------------------------------------------------------------
    protection_level = models.CharField(
        verbose_name='保护级别',
        max_length=4,
        choices=PROTECTION_LEVEL_CHOICES,
        help_text='文物保护单位级别，尚未核定的选"尚未定级的不可移动文物"',
    )
    protection_announced_batch = models.CharField(
        verbose_name='公布批次',
        max_length=50,
        blank=True,
        default='',
        help_text='核定公布的批次，如"第八批全国重点文物保护单位"',
    )
    protection_announced_date = models.DateField(
        verbose_name='公布日期',
        null=True,
        blank=True,
        help_text='文物保护单位核定公布的日期',
    )
    has_marker_stele = models.BooleanField(
        verbose_name='是否有保护标志碑',
        default=False,
        help_text='现场是否已设立保护标志碑',
    )
    has_protection_zone_announced = models.BooleanField(
        verbose_name='是否已公布保护范围',
        default=False,
        help_text='是否经政府正式公布保护范围（四至范围）',
    )
    has_construction_control_zone_announced = models.BooleanField(
        verbose_name='是否已公布建设控制地带',
        default=False,
        help_text='是否经政府正式公布建设控制地带',
    )

    # ------------------------------------------------------------------
    # 八、文物简介（长文本）
    # ------------------------------------------------------------------
    description = models.TextField(
        verbose_name='文物简介',
        blank=True,
        default='',
        help_text='文物的历史背景、形制特征、价值与现状的综合描述，建议300字以上',
    )
    remarks = models.TextField(
        verbose_name='备注',
        blank=True,
        default='',
        help_text='其他需要补充说明的事项',
    )

    # ------------------------------------------------------------------
    # 九、普查工作信息（采集/录入/审核）
    # ------------------------------------------------------------------
    collector = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_heritages',
        verbose_name='采集人',
        help_text='现场数据采集人员（系统用户）',
    )
    collected_at = models.DateTimeField(
        verbose_name='采集时间',
        null=True,
        blank=True,
        help_text='现场采集数据的日期与时间',
    )
    input_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inputted_heritages',
        verbose_name='录入人',
        help_text='将数据录入系统的操作人员',
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_heritages',
        verbose_name='审核人',
        help_text='对登记信息进行审核确认的人员',
    )
    reviewed_at = models.DateTimeField(
        verbose_name='审核时间',
        null=True,
        blank=True,
        help_text='审核完成的日期与时间',
    )
    created_at = models.DateTimeField(
        verbose_name='创建时间',
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name='最后更新时间',
        auto_now=True,
    )

    def __str__(self):
        return f'[{self.survey_code}] {self.name}（{self.era}）'

    def _generate_next_collection_code(self) -> str:
        """生成年度顺序采集编号：SS-CJ-YYYY-NNNN。"""
        year = (self.collected_at or timezone.now()).year
        prefix = f"SS-CJ-{year}-"

        latest_code = (
            self.__class__.objects
            .filter(survey_code__startswith=prefix)
            .order_by('-survey_code')
            .values_list('survey_code', flat=True)
            .first()
        )

        seq = 1
        if latest_code:
            match = re.match(rf"^{re.escape(prefix)}(\d{{4}})$", latest_code)
            if match:
                seq = int(match.group(1)) + 1

        return f"{prefix}{seq:04d}"

    def save(self, *args, **kwargs):
        # 手工填写时沿用手工值；为空时自动生成并发安全的顺序编号。
        self.survey_code = (self.survey_code or '').strip()
        if self.survey_code:
            return super().save(*args, **kwargs)

        last_error = None
        for _ in range(8):
            self.survey_code = self._generate_next_collection_code()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                last_error = exc
                self.survey_code = ''

        if last_error:
            raise last_error
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = '不可移动文物登记表（四普）'
        verbose_name_plural = verbose_name
        ordering = ['survey_code']
        indexes = [
            models.Index(fields=['survey_code']),
            models.Index(fields=['category']),
            models.Index(fields=['protection_level']),
            models.Index(fields=['province', 'city', 'county']),
        ]


class HeritagePhoto(models.Model):
    """
    文物点现场照片（一对多，关联 ImmovableHeritage）。
    每张照片独立记录拍摄信息、上传人，支持按类型分类管理。
    """

    PHOTO_TYPE_CHOICES = [
        ('overview',  '全景照'),
        ('detail',    '局部/细节照'),
        ('aerial',    '航拍照'),
        ('signage',   '保护标志碑照'),
        ('damage',    '损毁情况照'),
        ('surroundings', '周边环境照'),
        ('other',     '其他'),
    ]

    DIRECTION_CHOICES = [
        ('E',  '朝东'),
        ('W',  '朝西'),
        ('S',  '朝南'),
        ('N',  '朝北'),
        ('NE', '朝东北'),
        ('NW', '朝西北'),
        ('SE', '朝东南'),
        ('SW', '朝西南'),
        ('',   '不详'),
    ]

    heritage = models.ForeignKey(
        ImmovableHeritage,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name='所属文物点',
        help_text='照片归属的不可移动文物登记记录',
    )
    image = models.ImageField(
        verbose_name='照片文件',
        upload_to='heritage_photos/%Y/%m/',
        help_text='建议上传JPG/PNG格式，分辨率不低于1920×1080，文件大小不超过10MB',
    )
    photo_type = models.CharField(
        verbose_name='照片类型',
        max_length=20,
        choices=PHOTO_TYPE_CHOICES,
        default='overview',
        help_text='照片拍摄内容的类型分类',
    )
    direction = models.CharField(
        verbose_name='拍摄方向',
        max_length=2,
        choices=DIRECTION_CHOICES,
        blank=True,
        default='',
        help_text='相机朝向，用于描述拍摄角度',
    )
    caption = models.CharField(
        verbose_name='照片说明',
        max_length=300,
        blank=True,
        default='',
        help_text='对照片内容的简要文字说明',
    )
    shot_at = models.DateTimeField(
        verbose_name='拍摄时间',
        null=True,
        blank=True,
        help_text='照片的实际拍摄日期与时间（可从EXIF读取）',
    )
    shot_longitude = models.DecimalField(
        verbose_name='拍摄点经度',
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='拍摄时的GPS经度，可从EXIF自动提取',
    )
    shot_latitude = models.DecimalField(
        verbose_name='拍摄点纬度',
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        help_text='拍摄时的GPS纬度，可从EXIF自动提取',
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_heritage_photos',
        verbose_name='上传人',
        help_text='将照片上传至系统的操作人员',
    )
    uploaded_at = models.DateTimeField(
        verbose_name='上传时间',
        auto_now_add=True,
    )
    is_cover = models.BooleanField(
        verbose_name='是否为封面图',
        default=False,
        help_text='勾选后此照片将作为该文物点的代表图片显示',
    )

    def __str__(self):
        return f'{self.heritage.name} - {self.get_photo_type_display()} ({self.uploaded_at.strftime("%Y-%m-%d")})'

    class Meta:
        verbose_name = '文物点现场照片'
        verbose_name_plural = verbose_name
        ordering = ['-is_cover', '-shot_at', '-uploaded_at']
        indexes = [
            models.Index(fields=['heritage', 'photo_type']),
            models.Index(fields=['heritage', 'is_cover']),
        ]
