from django.contrib import admin

from system.models import DictionaryItem, DictionaryType, LoginLog, Menu, OperationLog, SystemConfig


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'menu_type', 'path', 'parent', 'order_num', 'visible', 'is_active')
    list_filter = ('menu_type', 'visible', 'is_active')
    search_fields = ('name', 'path', 'permission_code')
    filter_horizontal = ('roles',)


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'success', 'ip', 'created_at')
    list_filter = ('success',)
    search_fields = ('username', 'ip', 'message')


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'module', 'action', 'operator', 'success', 'created_at')
    list_filter = ('module', 'action', 'success')
    search_fields = ('module', 'action', 'request_path', 'detail')


@admin.register(DictionaryType)
class DictionaryTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'name', 'is_active', 'updated_at')
    search_fields = ('code', 'name')
    list_filter = ('is_active',)


@admin.register(DictionaryItem)
class DictionaryItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'dict_type', 'label', 'value', 'order_num', 'is_active')
    list_filter = ('dict_type', 'is_active')
    search_fields = ('label', 'value')


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'key', 'value_type', 'is_public', 'updated_at')
    search_fields = ('key', 'value', 'remark')
    list_filter = ('value_type', 'is_public')
