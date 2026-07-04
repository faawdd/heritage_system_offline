from django.urls import path

from system.views import (
    DeepSeekConfigAPIView,
    ChangePasswordAPIView,
    LoginLogListAPIView,
    MenuListAPIView,
    MenuDetailAPIView,
    OperationLogListAPIView,
    PermissionListAPIView,
    RoleListAPIView,
    SystemAdminEntryAPIView,
    RoleMenuAPIView,
    RolePermissionAPIView,
    SystemLoginAPIView,
    SystemLogoutAPIView,
    SystemPublicConfigAPIView,
    SystemProfileAPIView,
    SystemRefreshAPIView,
    UserDetailAPIView,
    UserListCreateAPIView,
)

app_name = 'system'

urlpatterns = [
    path('login/', SystemLoginAPIView.as_view(), name='login'),
    path('refresh/', SystemRefreshAPIView.as_view(), name='refresh'),
    path('public-config/', SystemPublicConfigAPIView.as_view(), name='public_config'),
    path('logout/', SystemLogoutAPIView.as_view(), name='logout'),
    path('admin-entry/', SystemAdminEntryAPIView.as_view(), name='admin_entry'),
    path('profile/', SystemProfileAPIView.as_view(), name='profile'),
    path('profile/change-password/', ChangePasswordAPIView.as_view(), name='change_password'),
    path('users/', UserListCreateAPIView.as_view(), name='users'),
    path('users/<int:user_id>/', UserDetailAPIView.as_view(), name='user_detail'),
    path('roles/', RoleListAPIView.as_view(), name='roles'),
    path('roles/<int:role_id>/permissions/', RolePermissionAPIView.as_view(), name='role_permissions'),
    path('roles/<int:role_id>/menus/', RoleMenuAPIView.as_view(), name='role_menus'),
    path('permissions/', PermissionListAPIView.as_view(), name='permissions'),
    path('menus/', MenuListAPIView.as_view(), name='menus'),
    path('menus/<int:menu_id>/', MenuDetailAPIView.as_view(), name='menu_detail'),
    path('login-log/', LoginLogListAPIView.as_view(), name='login_log'),
    path('operation-log/', OperationLogListAPIView.as_view(), name='operation_log'),
    path('ai-config/deepseek/', DeepSeekConfigAPIView.as_view(), name='deepseek_config'),
]
