from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = '文物业务管理'  # 添加这一行    
    def ready(self):
        """Django启动时加载signals"""
        import core.signals