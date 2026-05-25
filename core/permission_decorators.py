"""
权限装饰器和工具函数 - 用于视图级别和模板级别的权限控制

=== 权限体系说明 ===
三层权限结构：
  🔵 看护员    - 仅巡查上报 (最小化权限)
  🟡 管理员    - 大部分管理功能 (不影响数据安全)
  🔴 超级管理员 - 完全访问

=== 使用方式 ===

1. 视图装饰器 - 用于保护视图
   @admin_required
   def project_list(request): ...

2. 工具函数 - 用于权限检查
   if is_admin(request.user):
       # 管理员相关操作

3. 模板过滤器 - 用于模板显示
   {% if user|has_group:"管理员" %}
"""
from functools import wraps
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django import template

register = template.Library()


GROUP_ADMIN = '管理员'
GROUP_LIMITED_ADMIN = '管理员用户组'
GROUP_SUPER_ADMIN = '超级管理员'
GROUP_INSPECTOR = '文物看护员'


# ============================================================================
# 视图装饰器
# ============================================================================

def group_required(*group_names):
    """
    验证用户是否属于指定的用户组（装饰器）
    
    用法:
        @group_required('管理员', '超级管理员')
        def my_view(request):
            ...
    
    说明：
        - 允许超级管理员直接访问
        - 支持多个用户组，满足其中任一个即可
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            user_groups = request.user.groups.values_list('name', flat=True)
            if request.user.is_superuser or any(g in user_groups for g in group_names):
                return view_func(request, *args, **kwargs)
            
            # 返回403禁止访问
            return render(request, '403.html', {
                'message': f'需要用户组权限: {", ".join(group_names)}'
            }, status=403)
        
        return wrapper
    return decorator


def inspector_required(view_func):
    """
    验证用户是否为文物看护员（装饰器）
    
    允许访问的用户组：
        ✓ 看护员
        ✓ 管理员  
        ✓ 超级管理员
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        is_inspector = request.user.groups.filter(name=GROUP_INSPECTOR).exists()
        is_admin = request.user.groups.filter(name=GROUP_ADMIN).exists()
        
        if request.user.is_superuser or is_inspector or is_admin:
            return view_func(request, *args, **kwargs)
        
        return render(request, '403.html', {
            'message': '需要文物看护员权限才能提交巡查报告'
        }, status=403)
    
    return wrapper


def admin_required(view_func):
    """
    验证用户是否为管理员或超级管理员（装饰器）
    
    允许访问的用户组：
        ✓ 管理员
        ✓ 超级管理员
    
    拒绝访问的用户组：
        ✗ 看护员
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        is_admin = request.user.groups.filter(name=GROUP_ADMIN).exists()
        is_limited_admin = request.user.groups.filter(name=GROUP_LIMITED_ADMIN).exists()
        
        if request.user.is_superuser or is_admin or is_limited_admin:
            return view_func(request, *args, **kwargs)
        
        return render(request, '403.html', {
            'message': '需要管理员权限'
        }, status=403)
    
    return wrapper


def super_admin_required(view_func):
    """
    验证用户是否为超级管理员（装饰器）
    
    仅允许：✓ 超级管理员
    
    拒绝所有其他用户
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        return render(request, '403.html', {
            'message': '需要超级管理员权限'
        }, status=403)
    
    return wrapper


# ============================================================================
# 工具函数 - 权限检查
# ============================================================================

def has_group(user, *group_names):
    """
    检查用户是否属于指定的用户组（工具函数）
    
    用法:
        if has_group(request.user, '管理员', '超级管理员'):
            # 允许访问
    
    特殊说明：
        - 超级管理员自动返回 True
        - 支持检查多个用户组
    """
    if user.is_superuser:
        return True
    user_groups = user.groups.values_list('name', flat=True)
    return any(g in user_groups for g in group_names)


def is_super_admin(user):
    """
    检查用户是否为超级管理员
    
    返回：True/False
    """
    return user.is_superuser


def is_admin(user):
    """
    检查用户是否为管理员或超级管理员
    
    返回：True/False
    
    包含用户组：
        - 超级管理员 (Django is_superuser)
        - 管理员 (Group name='管理员')
    """
    return user.is_superuser or user.groups.filter(name=GROUP_ADMIN).exists()


def is_limited_admin(user):
    """
    检查用户是否为“管理员用户组”（受限管理角色）

    返回：True/False
    """
    return user.groups.filter(name=GROUP_LIMITED_ADMIN).exists()


def is_management_admin(user):
    """
    检查用户是否具备管理入口权限

    包含：
        - 超级管理员
        - 管理员
        - 管理员用户组
    """
    return is_admin(user) or is_limited_admin(user)


def can_modify_core_data(user):
    """
    检查用户是否允许修改底层核心数据

    允许：
        - 超级管理员
        - 管理员

    不允许：
        - 管理员用户组
        - 文物看护员
    """
    return is_admin(user)


def is_inspector(user):
    """
    检查用户是否为文物看护员
    
    返回：True/False
    
    仅检查：文物看护员 (Group name='文物看护员')
    """
    return user.groups.filter(name=GROUP_INSPECTOR).exists()


def get_user_role(user):
    """
    获取用户的角色描述
    
    返回值：
        '超级管理员' - Django超级用户
        '管理员'     - 在管理员用户组中
        '看护员'     - 在文物看护员用户组中
        '普通用户'   - 未分配任何用户组
    """
    if user.is_superuser:
        return '超级管理员'
    elif user.groups.filter(name=GROUP_ADMIN).exists():
        return '管理员'
    elif user.groups.filter(name=GROUP_LIMITED_ADMIN).exists():
        return '管理员用户组'
    elif user.groups.filter(name=GROUP_INSPECTOR).exists():
        return '看护员'
    else:
        return '普通用户'


def get_permissions_summary(user):
    """
    获取用户权限摘要
    
    返回字典：{
        'role': '用户角色',
        'is_superuser': bool,
        'is_admin': bool,
        'is_inspector': bool,
        'groups': ['用户组1', '用户组2', ...],
        'permission_count': 权限数量,
    }
    """
    return {
        'role': get_user_role(user),
        'is_superuser': is_super_admin(user),
        'is_admin': is_admin(user),
        'is_limited_admin': is_limited_admin(user),
        'is_management_admin': is_management_admin(user),
        'is_inspector': is_inspector(user),
        'can_modify_core_data': can_modify_core_data(user),
        'groups': list(user.groups.values_list('name', flat=True)),
        'permission_count': user.user_permissions.count() if hasattr(user, 'user_permissions') else 0,
    }


# ============================================================================
# 模板过滤器和标签 - 用于模板中
# ============================================================================

@register.filter
def has_group_filter(user, group_name):
    """
    模板过滤器：检查用户是否属于某个用户组
    
    用法（在模板中）:
        {% if user|has_group_filter:"管理员" %}
            <a href="...">管理面板</a>
        {% endif %}
    """
    return has_group(user, group_name)


@register.filter
def user_role(user):
    """
    模板过滤器：获取用户角色
    
    用法（在模板中）:
        <p>您的角色是：{{ user|user_role }}</p>
    """
    return get_user_role(user)


@register.simple_tag
def can_manage_projects(user):
    """
    模板标签：检查用户是否可以管理项目
    
    用法（在模板中）:
        {% can_manage_projects user as can_manage %}
        {% if can_manage %}...{% endif %}
    """
    return is_management_admin(user)


@register.simple_tag
def can_submit_inspection(user):
    """
    模板标签：检查用户是否可以提交巡查记录
    
    用法（在模板中）:
        {% can_submit_inspection user as can_submit %}
        {% if can_submit %}...{% endif %}
    """
    return is_inspector(user) or is_admin(user)

