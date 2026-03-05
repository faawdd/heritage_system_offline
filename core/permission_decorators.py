"""
权限装饰器 - 用于视图级别的权限控制
"""
from functools import wraps
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden
from django.shortcuts import render


def group_required(*group_names):
    """
    验证用户是否属于指定的用户组
    
    用法:
        @group_required('管理员', '超级管理员')
        def my_view(request):
            ...
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
    验证用户是否为文物看护员（用于巡查报告功能）
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        is_inspector = request.user.groups.filter(name='文物看护员').exists()
        is_admin = request.user.groups.filter(name='管理员').exists()
        
        if request.user.is_superuser or is_inspector or is_admin:
            return view_func(request, *args, **kwargs)
        
        return render(request, '403.html', {
            'message': '需要文物看护员权限才能提交巡查报告'
        }, status=403)
    
    return wrapper


def admin_required(view_func):
    """
    验证用户是否为管理员或超级管理员
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        is_admin = request.user.groups.filter(name='管理员').exists()
        
        if request.user.is_superuser or is_admin:
            return view_func(request, *args, **kwargs)
        
        return render(request, '403.html', {
            'message': '需要管理员权限'
        }, status=403)
    
    return wrapper


def super_admin_required(view_func):
    """
    验证用户是否为超级管理员
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


def has_group(user, *group_names):
    """
    工具函数 - 检查用户是否属于指定的用户组
    
    用法:
        if has_group(request.user, '管理员', '超级管理员'):
            ...
    """
    if user.is_superuser:
        return True
    user_groups = user.groups.values_list('name', flat=True)
    return any(g in user_groups for g in group_names)


def is_super_admin(user):
    """检查用户是否为超级管理员"""
    return user.is_superuser


def is_admin(user):
    """检查用户是否为管理员或超级管理员"""
    return user.is_superuser or user.groups.filter(name='管理员').exists()


def is_inspector(user):
    """检查用户是否为文物看护员"""
    return user.groups.filter(name='文物看护员').exists()
