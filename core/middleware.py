"""
中间件：检查用户首次登录并显示修改密码提示 + 自动设备检测重定向
"""
from django.contrib import messages
from django.urls import reverse
from django.shortcuts import redirect
from .models import UserProfile
from django.utils.html import format_html
from .device_detector import is_mobile_device


class FirstLoginPasswordChangeMiddleware:
    """
    在用户首次登录时显示提示，建议修改密码
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 只处理已认证用户
        if request.user.is_authenticated:
            try:
                profile = UserProfile.objects.get(user=request.user)
                
                # 如果用户首次登录但还没有改密码
                if (profile.first_login_at is not None and 
                    not profile.has_changed_password and
                    'change_password' not in request.path and
                    '/admin/password_change/' not in request.path):
                    
                    # 创建密码修改提示
                    change_password_url = reverse('admin:password_change')
                    message_html = format_html(
                        '⚠️ <strong>首次登录提示：</strong> 为了保护您的账户安全，'
                        '建议立即修改初始密码。'
                        '<a href="{}" style="margin-left: 10px; color: white; text-decoration: underline;">'
                        '立即修改</a>',
                        change_password_url
                    )
                    messages.warning(request, message_html)
                    
            except UserProfile.DoesNotExist:
                # 如果不存在profile，忽略
                pass
            except Exception as e:
                # 记录错误但不影响用户体验
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"FirstLoginPasswordChangeMiddleware 错误: {str(e)}")

        response = self.get_response(request)
        return response


class DeviceAutoRedirectMiddleware:
    """
    自动设备检测中间件 - 根据设备类型重定向到对应页面
    手机用户访问后台首页时自动跳转到 /mobile/add/
    支持 force_desktop=1 参数强制显示桌面版
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 仅处理 GET 请求，避免影响表单提交等操作
        if request.method != 'GET':
            return self.get_response(request)

        # force_desktop=1 时写入会话，后续请求持续使用桌面版
        if request.GET.get('force_desktop') == '1':
            request.session['force_desktop'] = True
        elif request.GET.get('force_desktop') == '0':
            request.session.pop('force_desktop', None)

        # 用户强制桌面版时，不进行手机重定向
        if request.session.get('force_desktop'):
            return self.get_response(request)

        # 只为已认证用户处理设备检测
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 仅手机设备触发重定向
        if not is_mobile_device(request):
            return self.get_response(request)

        current_path = request.path

        # 不重定向以下路径，避免循环或影响认证流程
        no_redirect_prefixes = ['/mobile/', '/static/', '/media/', '/api/']
        if any(current_path.startswith(prefix) for prefix in no_redirect_prefixes):
            return self.get_response(request)

        no_redirect_admin_paths = [
            '/admin/login/',
            '/admin/logout/',
            '/admin/password_change/',
            '/admin/password_change/done/',
        ]
        if current_path in no_redirect_admin_paths:
            return self.get_response(request)

        # 手机端访问后台首页时，跳转到手机端系统入口
        if current_path in ['/admin/', '/admin/home/']:
            return redirect('/mobile/add/')
        
        response = self.get_response(request)
        return response


class AdminFullPathGateMiddleware:
    """
    Django Admin 全路径门禁：
    - 仅允许通过 Vue 系统入口建立的 SSO 会话访问 /admin/*
    - 其他直接访问统一重定向到 Vue 登录/受控入口
    """

    VUE_LOGIN_REDIRECT = '/?redirect=/system/admin'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''

        if not path.startswith('/admin/'):
            return self.get_response(request)

        # 仅放行已认证、具备后台权限且携带Vue入口会话标记的请求。
        user = getattr(request, 'user', None)
        is_authenticated = bool(user and user.is_authenticated)
        has_admin_permission = bool(is_authenticated and (user.is_staff or user.is_superuser))
        has_vue_sso_flag = bool(request.session.get('admin_sso_from_vue'))

        if has_admin_permission and has_vue_sso_flag:
            return self.get_response(request)

        return redirect(self.VUE_LOGIN_REDIRECT)
