"""内置用户组（角色）模板：供 init_user_groups 命令与角色管理 API 共用。

模板 key 即内置用户组名称。访问级别（管理端入口、能否修改核心数据）由
permission_decorators 中的组名判定，因此内置组不允许改名或删除。
"""
from django.contrib.auth.models import Group, Permission

from core.permission_decorators import (
    GROUP_ADMIN,
    GROUP_INSPECTOR,
    GROUP_LIMITED_ADMIN,
    GROUP_SUPER_ADMIN,
)

INSPECTOR_PERMISSIONS = [
    'view_heritagesite',
    'add_inspectionrecord',
    'change_inspectionrecord',
    'view_inspectionrecord',
    'change_userprofile',
    'view_userprofile',
]

ADMIN_PERMISSIONS = [
    'add_heritagesite',
    'change_heritagesite',
    'view_heritagesite',
    'add_inspectionrecord',
    'change_inspectionrecord',
    'view_inspectionrecord',
    'delete_inspectionrecord',
    'add_projectaudit',
    'change_projectaudit',
    'view_projectaudit',
    'delete_projectaudit',
    'add_coordinate',
    'change_coordinate',
    'view_coordinate',
    'delete_coordinate',
    'add_user',
    'change_user',
    'view_user',
    'add_group',
    'change_group',
    'view_group',
    'add_userprofile',
    'change_userprofile',
    'view_userprofile',
]

LIMITED_ADMIN_PERMISSIONS = [
    'view_heritagesite',
    'view_inspectionrecord',
    'add_projectaudit',
    'change_projectaudit',
    'view_projectaudit',
    'delete_projectaudit',
    'add_coordinate',
    'change_coordinate',
    'view_coordinate',
    'delete_coordinate',
    'add_kmluploadrecord',
    'change_kmluploadrecord',
    'view_kmluploadrecord',
    'delete_kmluploadrecord',
    'view_immovableheritage',
    'view_heritagephoto',
    'view_user',
    'view_group',
    'view_userprofile',
    'view_usermanagementaudit',
]

ROLE_TEMPLATES = {
    GROUP_ADMIN: {
        'label': '内置管理员',
        'description': '文保科工作人员和领导，拥有大部分管理权限（可修改核心业务数据）',
        'permissions': ADMIN_PERMISSIONS,
        'menu_paths': None,
    },
    GROUP_INSPECTOR: {
        'label': '文物看护员',
        'description': '巡查人员，仅能使用文物点巡查上报功能',
        'permissions': INSPECTOR_PERMISSIONS,
        'menu_paths': [
            '/dashboard',
            '/heritage/map',
            '/heritage/inspections',
            '/heritage/inspections/new',
        ],
    },
    GROUP_LIMITED_ADMIN: {
        'label': '管理员用户组（只读）',
        'description': '可执行大部分管理操作，但仅能查看文物点和巡查底层数据，不能修改',
        'permissions': LIMITED_ADMIN_PERMISSIONS,
        'menu_paths': None,
    },
}

BUILTIN_GROUP_NAMES = frozenset(ROLE_TEMPLATES) | {GROUP_SUPER_ADMIN}


def is_builtin_group(group):
    return group.name in BUILTIN_GROUP_NAMES


def resolve_permissions(codenames):
    """按 codename 查找权限，返回 (权限列表, 缺失的 codename 列表)。"""
    found, missing = [], []
    for codename in codenames:
        perm = Permission.objects.filter(codename=codename).order_by('id').first()
        if perm is None:
            missing.append(codename)
        else:
            found.append(perm)
    return found, missing


def apply_role_template(group, template_key):
    """把模板权限（及可选菜单）写入用户组，返回 (权限数, 缺失 codename 列表)。"""
    template = ROLE_TEMPLATES[template_key]
    permissions, missing = resolve_permissions(template['permissions'])
    group.permissions.set(permissions)

    menu_paths = template.get('menu_paths')
    if menu_paths:
        from system.models import Menu

        for menu in Menu.objects.filter(path__in=menu_paths):
            menu.roles.add(group)
    return len(permissions), missing


def ensure_builtin_groups():
    """确保内置用户组存在且权限与模板一致，返回已处理的组。"""
    groups = []
    for name in ROLE_TEMPLATES:
        group, _ = Group.objects.get_or_create(name=name)
        apply_role_template(group, name)
        groups.append(group)
    return groups
