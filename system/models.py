from django.conf import settings
from django.db import models


class Menu(models.Model):
    MENU_TYPE_CHOICES = [
        ('directory', '目录'),
        ('menu', '菜单'),
        ('button', '按钮'),
    ]

    name = models.CharField('菜单名称', max_length=100)
    path = models.CharField('路由路径', max_length=255, blank=True, default='')
    component = models.CharField('前端组件', max_length=255, blank=True, default='')
    icon = models.CharField('图标', max_length=64, blank=True, default='')
    permission_code = models.CharField('权限标识', max_length=100, blank=True, default='')
    menu_type = models.CharField('类型', max_length=20, choices=MENU_TYPE_CHOICES, default='menu')
    visible = models.BooleanField('是否显示', default=True)
    keep_alive = models.BooleanField('是否缓存', default=False)
    order_num = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='children',
        null=True,
        blank=True,
        verbose_name='父级菜单',
    )
    roles = models.ManyToManyField('auth.Group', blank=True, related_name='system_menus', verbose_name='角色')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '系统菜单'
        verbose_name_plural = verbose_name
        ordering = ['order_num', 'id']
        indexes = [
            models.Index(fields=['parent', 'order_num']),
            models.Index(fields=['path']),
            models.Index(fields=['is_active', 'visible']),
        ]

    def __str__(self):
        return self.name


class LoginLog(models.Model):
    username = models.CharField('用户名', max_length=150)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_login_logs',
        verbose_name='用户',
    )
    success = models.BooleanField('是否成功', default=False)
    ip = models.GenericIPAddressField('IP地址', null=True, blank=True)
    user_agent = models.CharField('User-Agent', max_length=512, blank=True, default='')
    message = models.CharField('结果说明', max_length=255, blank=True, default='')
    created_at = models.DateTimeField('登录时间', auto_now_add=True)

    class Meta:
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['success']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.username} - {"成功" if self.success else "失败"}'


class OperationLog(models.Model):
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_operation_logs',
        verbose_name='操作人',
    )
    module = models.CharField('模块', max_length=100)
    action = models.CharField('动作', max_length=100)
    method = models.CharField('请求方法', max_length=16, blank=True, default='')
    request_path = models.CharField('请求路径', max_length=255, blank=True, default='')
    ip = models.GenericIPAddressField('IP地址', null=True, blank=True)
    success = models.BooleanField('是否成功', default=True)
    detail = models.TextField('详情', blank=True, default='')
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['module', 'action']),
            models.Index(fields=['operator']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.module}:{self.action}'


class DictionaryType(models.Model):
    code = models.CharField('字典类型编码', max_length=64, unique=True)
    name = models.CharField('字典类型名称', max_length=100)
    remark = models.CharField('备注', max_length=255, blank=True, default='')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '字典类型'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class DictionaryItem(models.Model):
    dict_type = models.ForeignKey(DictionaryType, on_delete=models.CASCADE, related_name='items', verbose_name='字典类型')
    label = models.CharField('显示文本', max_length=100)
    value = models.CharField('字典值', max_length=100)
    order_num = models.IntegerField('排序', default=0)
    is_default = models.BooleanField('是否默认', default=False)
    is_active = models.BooleanField('是否启用', default=True)
    remark = models.CharField('备注', max_length=255, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '字典项'
        verbose_name_plural = verbose_name
        ordering = ['order_num', 'id']
        unique_together = [('dict_type', 'value')]

    def __str__(self):
        return f'{self.dict_type.code}:{self.value}'


class SystemConfig(models.Model):
    key = models.CharField('配置键', max_length=100, unique=True)
    value = models.TextField('配置值', blank=True, default='')
    value_type = models.CharField('值类型', max_length=30, default='string')
    remark = models.CharField('备注', max_length=255, blank=True, default='')
    is_public = models.BooleanField('前端可见', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name
        ordering = ['key']

    def __str__(self):
        return self.key
