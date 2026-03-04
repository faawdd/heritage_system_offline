from django.db import models
from django.contrib.auth.models import User

# 1. 不可移动文物基础表（结合四普字段）
class HeritageSite(models.Model):
    CATEGORY_CHOICES = [
        ('GYZ', '古文化遗址'), ('GMZ', '古墓葬'), ('GJZ', '古建筑'),
        ('SKT', '石窟寺及石刻'), ('JDJW', '近现代重要史迹及代表性建筑'), ('QT', '其他')
    ]
    LEVEL_CHOICES = [('GB', '全国重点文物保护单位'), ('SB', '自治区级文物保护单位'), ('XB', '县级文物保护单位'), ('DS', '尚未定级的不可移动文物')]

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

    class Meta:
        verbose_name = "不可移动文物档案"
        verbose_name_plural = verbose_name

    # 新增：两线坐标数据 (存储为 JSON 字符串，例如: "[[116.1, 39.1], [116.2, 39.1], ...]")
    protection_zone = models.TextField("保护范围坐标集合", null=True,blank=True, help_text="请输入经纬度序列JSON")
    control_zone = models.TextField("建控地带坐标集合", null=True, blank=True)

    def is_inside_zones(self, lon, lat):
        """判断给定的点是否落入两线"""
        p = Point(lon, lat)
        results = {"in_protection": False, "in_control": False}
        
        # 检查保护范围
        if self.protection_zone:
            poly = Polygon(json.loads(self.protection_zone))
            if poly.contains(p):
                results["in_protection"] = True
        
        # 检查建控地带
        if self.control_zone:
            poly = Polygon(json.loads(self.control_zone))
            if poly.contains(p):
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

    class Meta:
        verbose_name = "巡查登记存档"
        verbose_name_plural = verbose_name

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


# 4. 用户配置文件（追踪首次登录）
class UserProfile(models.Model):
    """追踪用户首次登录，提示修改密码"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    has_changed_password = models.BooleanField("是否已修改密码", default=False)
    first_login_at = models.DateTimeField("首次登录时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - 已改密: {self.has_changed_password}"
    
    class Meta:
        verbose_name = "用户密码修改记录"
        verbose_name_plural = verbose_name
