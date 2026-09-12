"""DRF 权限类。

安全约定
--------
本模块历史上曾用 ``settings.DEBUG and host in {127.0.0.1, localhost}`` 作为
"本地开发兜底"，对匿名请求无条件放行管理接口。由于离线桌面版
（``desktop_backend.py``）曾硬编码 ``DJANGO_DEBUG='1'``，该分支等价于
"出厂即允许本机任意进程无凭证读取全部业务数据"，属于越权风险。

现在管理权限只认 JWT / 会话认证后的真实角色。确有需要临时绕过时
（例如 Vite 热更新下不想走登录流程），必须显式设置环境变量
``HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1``，且请求来源仍须是回环地址。
"""
import os

from rest_framework.permissions import BasePermission

from core.permission_decorators import is_management_admin


def _is_loopback_host(request) -> bool:
    try:
        host = (request.get_host() or '').split(':')[0].strip('[]')
    except Exception:
        # get_host() 在 ALLOWED_HOSTS 不匹配时会抛 DisallowedHost，此时按非本机处理。
        return False
    return host in {'127.0.0.1', 'localhost', '::1'}


def local_debug_bypass_enabled() -> bool:
    """是否显式开启本地调试放行（默认关闭）。"""
    return str(os.environ.get('HERITAGE_DEV_ALLOW_LOCAL_BYPASS') or '').lower() in {'1', 'true', 'yes', 'on'}


class IsManagementAdmin(BasePermission):
    """Allow only users who already have management access in current role model."""

    message = '需要管理权限。'

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and is_management_admin(user):
            return True

        # 显式 opt-in 的本地调试兜底：避免 Vite 调试时没有认证会话被完全卡死。
        # 注意：不再由 settings.DEBUG 隐式触发，必须同时满足
        # HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1 + 回环来源 + 未认证请求。
        if local_debug_bypass_enabled() and _is_loopback_host(request):
            return True

        return False
