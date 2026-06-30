from rest_framework.permissions import BasePermission
from django.conf import settings

from core.permission_decorators import is_management_admin


class IsManagementAdmin(BasePermission):
    """Allow only users who already have management access in current role model."""

    message = '需要管理权限。'

    def has_permission(self, request, view):
        user = request.user
        if user and user.is_authenticated and is_management_admin(user):
            return True

        # Local development fallback: avoid blocking Vite debugging when no auth session exists.
        host = (request.get_host() or '').split(':')[0]
        if settings.DEBUG and host in {'127.0.0.1', 'localhost'}:
            return True

        return False
