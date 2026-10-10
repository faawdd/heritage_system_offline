from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from core.role_templates import ROLE_TEMPLATES
from system.admin_labels import VERBS, permission_name


LOG_PERMISSION_CODES = [
    'system.view_loginlog', 'system.view_operationlog', 'admin.view_logentry',
    'core.view_usermanagementaudit', 'core.view_landuseprojectoperationlog',
]


@receiver(post_migrate, dispatch_uid='system_admin_chinese_permissions')
def sync_admin_permissions(sender, using, **kwargs):
    permissions = list(Permission.objects.using(using).select_related('content_type'))
    changed = []
    for permission in permissions:
        verb, _, model = permission.codename.partition('_')
        if verb in VERBS and model == permission.content_type.model:
            label = permission_name(permission)
            if permission.name != label:
                permission.name = label
                changed.append(permission)
    if changed:
        Permission.objects.using(using).bulk_update(changed, ['name'])
    logs = [permission for permission in permissions
            if f'{permission.content_type.app_label}.{permission.codename}' in LOG_PERMISSION_CODES]
    for group in Group.objects.using(using).filter(name__in=[*ROLE_TEMPLATES, '超级管理员']):
        group.permissions.add(*logs)
        if group.name == '管理员':
            group.permissions.add(*[permission for permission in permissions
                                   if permission.content_type.app_label == 'auth' and permission.codename == 'delete_group'])
