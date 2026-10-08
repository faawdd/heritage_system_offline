from django.urls import path

from system.views import (
    DeepSeekConfigAPIView,
    ChangePasswordAPIView,
    ForgotPasswordQuestionsAPIView,
    ForgotPasswordResetAPIView,
    LoginLogListAPIView,
    MenuListAPIView,
    MenuDetailAPIView,
    OperationLogListAPIView,
    PermissionListAPIView,
    RoleListAPIView,
    RoleMenuAPIView,
    RolePermissionAPIView,
    SystemLoginAPIView,
    SystemLogoutAPIView,
    SystemProfileAPIView,
    SystemRefreshAPIView,
    SecurityQuestionBankAPIView,
    UserDetailAPIView,
    UserListCreateAPIView,
)

app_name = 'system'

urlpatterns = [
    path('login/', SystemLoginAPIView.as_view(), name='login'),
    path('security-questions/', SecurityQuestionBankAPIView.as_view(), name='security_questions'),
    path('forgot-password/questions/', ForgotPasswordQuestionsAPIView.as_view(), name='forgot_password_questions'),
    path('forgot-password/reset/', ForgotPasswordResetAPIView.as_view(), name='forgot_password_reset'),
    path('refresh/', SystemRefreshAPIView.as_view(), name='refresh'),
    path('logout/', SystemLogoutAPIView.as_view(), name='logout'),
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
