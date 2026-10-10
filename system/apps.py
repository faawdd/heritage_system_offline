from django.apps import AppConfig


class SystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'system'
    verbose_name = '系统管理'

    def ready(self):
        from system import admin_sync
