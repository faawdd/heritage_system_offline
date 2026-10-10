from django.contrib.auth.models import Group, User
from django.db.models import Q
from rest_framework.permissions import BasePermission

from core.permission_decorators import GROUP_ADMIN, GROUP_INSPECTOR, GROUP_LIMITED_ADMIN, GROUP_SUPER_ADMIN


def is_system_superuser(user):
    return bool(user.is_authenticated and (
        user.is_superuser or user.groups.filter(name=GROUP_SUPER_ADMIN).exists()
    ))


def has_system_permission(user, permission):
    return user.is_authenticated and (is_system_superuser(user) or user.has_perm(permission))


def management_capabilities(user):
    return {
        'view_groups': has_system_permission(user, 'auth.view_group'),
        'add_groups': has_system_permission(user, 'auth.add_group'),
        'change_groups': has_system_permission(user, 'auth.change_group'),
        'delete_groups': has_system_permission(user, 'auth.delete_group'),
        'view_users': has_system_permission(user, 'auth.view_user'),
        'add_users': has_system_permission(user, 'auth.add_user'),
        'change_users': has_system_permission(user, 'auth.change_user'),
        'delete_users': has_system_permission(user, 'auth.delete_user'),
        'view_logs': is_system_superuser(user) or any(user.has_perm(code) for code in [
            'system.view_loginlog', 'system.view_operationlog', 'admin.view_logentry',
            'core.view_usermanagementaudit', 'core.view_landuseprojectoperationlog',
        ]),
        'log_sources': [key for key, code in [
            ('login', 'system.view_loginlog'), ('operation', 'system.view_operationlog'),
            ('django', 'admin.view_logentry'), ('user', 'core.view_usermanagementaudit'),
            ('project', 'core.view_landuseprojectoperationlog'),
        ] if has_system_permission(user, code)],
    }


class GroupManagementPermission(BasePermission):
    message = '没有对应的用户组管理权限'

    def has_permission(self, request, view):
        action = {'GET': 'view', 'POST': 'add', 'PATCH': 'change', 'PUT': 'change', 'DELETE': 'delete'}.get(request.method)
        if getattr(view, 'template_action', False) and request.method == 'POST':
            action = 'change'
        return bool(action and has_system_permission(request.user, f'auth.{action}_group'))


class UserManagementPermission(BasePermission):
    message = '没有对应的用户管理权限，或不能操作权限高于自己的用户'

    def has_permission(self, request, view):
        action = {'GET': 'view', 'POST': 'add', 'PATCH': 'change', 'PUT': 'change', 'DELETE': 'delete'}.get(request.method)
        if not action or not has_system_permission(request.user, f'auth.{action}_user'):
            return False
        if request.method in {'GET', 'HEAD', 'OPTIONS'} or is_system_superuser(request.user):
            return True
        target = User.objects.filter(pk=view.kwargs.get('user_id')).first()
        if target and (
            is_system_superuser(target)
            or any(not request.user.has_perm(code) for code in target.get_all_permissions())
        ):
            return False
        ids = request.data.get('group_ids', [])
        if isinstance(ids, list) and all(isinstance(value, int) and not isinstance(value, bool) for value in ids):
            for group in Group.objects.filter(pk__in=ids).prefetch_related('permissions__content_type'):
                if group.name == GROUP_SUPER_ADMIN:
                    return False
                if any(not request.user.has_perm(f'{perm.content_type.app_label}.{perm.codename}')
                       for perm in group.permissions.all()):
                    return False
        return True


class PermissionCatalogPermission(BasePermission):
    message = '没有查看权限条目的权限'

    def has_permission(self, request, view):
        return has_system_permission(request.user, 'auth.view_group') or has_system_permission(request.user, 'auth.view_user')


def log_scope(user):
    if is_system_superuser(user):
        return None, '全部日志'
    users = User.objects.filter(pk=user.pk)
    if user.groups.filter(name__in=[GROUP_ADMIN, GROUP_LIMITED_ADMIN]).exists():
        inspectors = User.objects.filter(groups__name=GROUP_INSPECTOR, is_superuser=False).exclude(
            groups__name__in=[GROUP_ADMIN, GROUP_LIMITED_ADMIN, GROUP_SUPER_ADMIN]
        )
        users = User.objects.filter(Q(pk=user.pk) | Q(pk__in=inspectors.values('pk')))
        label = '本人及文物看护员日志'
    else:
        label = '本人日志'
    return users, label
