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

# 3. 工程建设核查表
class ProjectAudit(models.Model):
    project_name = models.CharField("建设项目名称", max_length=200)
    related_site = models.ForeignKey(HeritageSite, on_delete=models.CASCADE, verbose_name="涉及文物")
    # 拟建项目坐标
    project_lon = models.FloatField("项目经度")
    project_lat = models.FloatField("项目纬度")

    is_in_protection_zone = models.BooleanField("是否在保护范围内", default=False)
    is_in_control_zone = models.BooleanField("是否在建控地带内", default=False)
    audit_opinion = models.TextField("核查意见")
    status = models.CharField("审核状态", max_length=20, choices=[('Pending', '待审'), ('Pass', '通过'), ('Reject', '驳回')])
    file_archive = models.FileField("附件存档", upload_to='projects/docs/', blank=True)
    def save(self, *args, **kwargs):
        # 自动调用文物的判断逻辑
        check_res = self.related_site.is_inside_zones(self.project_lon, self.project_lat)
        self.is_in_protection_zone = check_res["in_protection"]
        self.is_in_control_zone = check_res["in_control"]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "工程建设核查"
        verbose_name_plural = verbose_name


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
