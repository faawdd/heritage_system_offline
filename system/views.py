from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group, Permission, User
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from core.permission_decorators import can_modify_core_data
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from core.models import UserProfile
from core.permissions.api_permissions import IsManagementAdmin
from core.role_templates import (
    BUILTIN_GROUP_NAMES,
    ROLE_TEMPLATES,
    apply_role_template,
    is_builtin_group,
    resolve_permissions,
)
from core.services.account_security import (
    LOGIN_LOCK_THRESHOLD,
    LOGIN_WAIT_SECONDS,
    LOGIN_WAIT_THRESHOLD,
    RECOVERY_WAIT_SECONDS,
    RECOVERY_WAIT_THRESHOLD,
    SECURITY_QUESTION_BANK,
    hash_security_questions,
    public_security_questions,
    verify_security_answers,
)
from system.models import LoginLog, Menu, OperationLog, SystemConfig
from system.admin_access import GroupManagementPermission, UserManagementPermission, has_system_permission
from system.log_api import LoginLogListAPIView, OperationLogListAPIView
from system.admin_api import PermissionCatalogAPIView as PermissionListAPIView
from system.serializers import (
    MenuSerializer,
    PermissionSerializer,
    ProfileSerializer,
    RoleSerializer,
    UserCreateUpdateSerializer,
    UserListSerializer,
)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _build_menu_tree(rows):
    by_parent = {}
    for row in rows:
        key = row['parent_id']
        by_parent.setdefault(key, []).append(row)

    def attach_children(parent_id):
        items = by_parent.get(parent_id, [])
        for item in items:
            children = attach_children(item['id'])
            item['children'] = children
        return items

    return attach_children(None)


def _record_operation(request, module, action, success=True, detail=''):
    user = request.user if request.user and request.user.is_authenticated else None
    OperationLog.objects.create(
        operator=user,
        module=module,
        action=action,
        method=request.method,
        request_path=request.path,
        ip=_get_client_ip(request),
        success=success,
        detail=(detail or '')[:2000],
    )


def _validate_id_list(raw_value, field_name):
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f'{field_name} 必须是数组')
    result = []
    for item in raw_value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            raise ValueError(f'{field_name} 包含非法ID')
    return result


def _forbid_if_no_write_permission(request, module, action):
    if module == 'system_role':
        verb = {'POST': 'add', 'PUT': 'change', 'PATCH': 'change', 'DELETE': 'delete'}.get(request.method)
        if action == 'apply_template':
            verb = 'change'
        if verb and has_system_permission(request.user, f'auth.{verb}_group'):
            return None
    if _is_super_admin_user(request.user) or can_modify_core_data(request.user):
        return None
    _record_operation(request, module, action, success=False, detail='管理员用户组仅可查看，禁止修改')
    return Response({'success': False, 'message': '当前角色仅可查看，禁止修改'}, status=status.HTTP_403_FORBIDDEN)


def _is_super_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='超级管理员').exists()


def _filter_menu_rows_for_user(rows, user):
    if _is_super_admin_user(user):
        return rows
    return [row for row in rows if (row.get('path') or '').strip() != '/system/menus']


def _forbid_if_not_super_admin(request, module, action):
    if _is_super_admin_user(request.user):
        return None
    _record_operation(request, module, action, success=False, detail='仅超级管理员可操作菜单管理')
    return Response({'success': False, 'message': '仅超级管理员可操作该功能'}, status=status.HTTP_403_FORBIDDEN)


class SystemLoginAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        ip = _get_client_ip(request)
        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]

        if not username or not password:
            LoginLog.objects.create(username=username or '-', success=False, ip=ip, user_agent=user_agent, message='缺少用户名或密码')
            return Response({'success': False, 'message': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        user_record = User.objects.filter(username=username).first()
        profile = UserProfile.objects.filter(user=user_record).first() if user_record else None
        now = timezone.now()
        if profile and profile.login_locked:
            LoginLog.objects.create(username=username, user=user_record, success=False, ip=ip, user_agent=user_agent, message='账户已锁定，请通过忘记密码重置')
            return Response({'success': False, 'message': '账户已锁定，请通过忘记密码验证安全问题并重置密码'}, status=423)
        if profile and profile.login_locked_until:
            if profile.login_locked_until > now:
                retry_after = max(1, int((profile.login_locked_until - now).total_seconds()))
                LoginLog.objects.create(username=username, user=user_record, success=False, ip=ip, user_agent=user_agent, message='登录尝试过多，账户暂时等待')
                return Response(
                    {'success': False, 'message': '连续输错次数过多，请稍后重试', 'retry_after': retry_after},
                    status=429,
                    headers={'Retry-After': str(retry_after)},
                )
            profile.login_locked_until = None
            profile.save(update_fields=['login_locked_until'])

        user = authenticate(request, username=username, password=password)
        if not user:
            if user_record and user_record.is_active:
                profile, _ = UserProfile.objects.get_or_create(user=user_record)
                profile.failed_login_attempts += 1
                if profile.failed_login_attempts >= LOGIN_LOCK_THRESHOLD:
                    profile.login_locked = True
                    profile.login_locked_until = None
                    failure_message = '账户已锁定，请通过忘记密码重置'
                    response_status = 423
                elif profile.failed_login_attempts >= LOGIN_WAIT_THRESHOLD:
                    profile.login_locked_until = now + timezone.timedelta(seconds=LOGIN_WAIT_SECONDS)
                    failure_message = '连续输错次数过多，请等待两分钟后重试'
                    response_status = 429
                else:
                    failure_message = '用户名或密码错误'
                    response_status = status.HTTP_401_UNAUTHORIZED
                profile.save(update_fields=['failed_login_attempts', 'login_locked_until', 'login_locked'])
            else:
                failure_message = '用户名或密码错误'
                response_status = status.HTTP_401_UNAUTHORIZED
            LoginLog.objects.create(username=username, success=False, ip=ip, user_agent=user_agent, message='用户名或密码错误')
            failure_data = {'success': False, 'message': failure_message}
            failure_response = Response(failure_data, status=response_status)
            if response_status == 429:
                failure_data['retry_after'] = LOGIN_WAIT_SECONDS
                failure_response['Retry-After'] = str(LOGIN_WAIT_SECONDS)
            return failure_response

        if not user.is_active:
            LoginLog.objects.create(username=username, user=user, success=False, ip=ip, user_agent=user_agent, message='用户已禁用')
            return Response({'success': False, 'message': '用户已禁用'}, status=status.HTTP_403_FORBIDDEN)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if len(profile.security_questions or []) != 3:
            raw_security_questions = request.data.get('security_questions')
            if not raw_security_questions:
                return Response(
                    {
                        'success': False,
                        'code': 'SECURITY_QUESTIONS_REQUIRED',
                        'message': '首次登录请先设置 3 个密码保护问题',
                    },
                    status=428,
                )
            try:
                profile.security_questions = hash_security_questions(raw_security_questions)
                profile.save(update_fields=['security_questions'])
            except DjangoValidationError as exc:
                return Response({'success': False, 'message': '；'.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        if profile.failed_login_attempts or profile.login_locked_until or profile.login_locked:
            profile.failed_login_attempts = 0
            profile.login_locked_until = None
            profile.login_locked = False
            profile.save(update_fields=['failed_login_attempts', 'login_locked_until', 'login_locked'])

        token_data = TokenObtainPairSerializer.get_token(user)
        access_token = str(token_data.access_token)
        refresh_token = str(token_data)

        LoginLog.objects.create(username=username, user=user, success=True, ip=ip, user_agent=user_agent, message='登录成功')

        menu_queryset = Menu.objects.filter(is_active=True, visible=True)
        if not user.is_superuser:
            menu_queryset = menu_queryset.filter(Q(roles__in=user.groups.all()) | Q(roles__isnull=True)).distinct()
        menu_rows = MenuSerializer(menu_queryset.order_by('order_num', 'id'), many=True).data
        menu_rows = _filter_menu_rows_for_user(list(menu_rows), user)

        return Response(
            {
                'success': True,
                'data': {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'user': ProfileSerializer(user).data,
                    'roles': list(user.groups.values_list('name', flat=True)),
                    'permissions': sorted(list(user.get_all_permissions())),
                    'menus': _build_menu_tree(list(menu_rows)),
                },
            }
        )


class SecurityQuestionBankAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response({'success': True, 'questions': SECURITY_QUESTION_BANK})


class ForgotPasswordQuestionsAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        username = str(request.data.get('username') or '').strip()
        user = User.objects.filter(username=username, is_active=True).first()
        profile = UserProfile.objects.filter(user=user).first() if user else None
        questions = public_security_questions(profile.security_questions if profile else [])
        if not questions:
            return Response({'success': False, 'message': '该账户尚未设置安全问题，请联系系统管理员'}, status=status.HTTP_400_BAD_REQUEST)
        if profile.recovery_locked_until and profile.recovery_locked_until > timezone.now():
            retry_after = max(1, int((profile.recovery_locked_until - timezone.now()).total_seconds()))
            return Response(
                {'success': False, 'message': '安全问题验证次数过多，请稍后重试'},
                status=429,
                headers={'Retry-After': str(retry_after)},
            )
        return Response({'success': True, 'questions': questions})


class ForgotPasswordResetAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        username = str(request.data.get('username') or '').strip()
        user = User.objects.filter(username=username, is_active=True).first()
        profile = UserProfile.objects.filter(user=user).first() if user else None
        if not profile or not public_security_questions(profile.security_questions):
            return Response({'success': False, 'message': '账户或安全问题答案不正确'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        if profile.recovery_locked_until and profile.recovery_locked_until > now:
            retry_after = max(1, int((profile.recovery_locked_until - now).total_seconds()))
            return Response(
                {'success': False, 'message': '安全问题验证次数过多，请稍后重试'},
                status=429,
                headers={'Retry-After': str(retry_after)},
            )

        if not verify_security_answers(profile.security_questions, request.data.get('answers')):
            profile.failed_recovery_attempts += 1
            response_status = status.HTTP_400_BAD_REQUEST
            response_message = '账户或安全问题答案不正确'
            if profile.failed_recovery_attempts >= RECOVERY_WAIT_THRESHOLD:
                profile.recovery_locked_until = now + timezone.timedelta(seconds=RECOVERY_WAIT_SECONDS)
                response_status = 429
                response_message = '安全问题答案错误次数过多，请等待 15 分钟后重试'
            profile.save(update_fields=['failed_recovery_attempts', 'recovery_locked_until'])
            response = Response(
                {'success': False, 'message': response_message},
                status=response_status,
            )
            if response_status == 429:
                response['Retry-After'] = str(RECOVERY_WAIT_SECONDS)
            return response

        new_password = str(request.data.get('new_password') or '')
        try:
            validate_password(new_password, user=user)
            questions_hash = hash_security_questions(request.data.get('security_questions'))
        except DjangoValidationError as exc:
            return Response({'success': False, 'message': '；'.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=['password'])
            profile.security_questions = questions_hash
            profile.has_changed_password = True
            profile.failed_login_attempts = 0
            profile.login_locked_until = None
            profile.login_locked = False
            profile.failed_recovery_attempts = 0
            profile.recovery_locked_until = None
            profile.save(update_fields=[
                'security_questions', 'has_changed_password', 'failed_login_attempts',
                'login_locked_until', 'login_locked', 'failed_recovery_attempts',
                'recovery_locked_until',
            ])

        return Response({'success': True, 'message': '密码已重置，请使用新密码登录'})


class SystemRefreshAPIView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'success': True, 'data': serializer.validated_data})


class SystemLogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'success': True, 'message': '已退出登录'})


class SystemProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'success': True, 'data': ProfileSerializer(request.user).data})

    def patch(self, request):
        user = request.user
        user.first_name = request.data.get('first_name', user.first_name)
        user.last_name = request.data.get('last_name', user.last_name)
        user.email = request.data.get('email', user.email)
        user.save(update_fields=['first_name', 'last_name', 'email'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if 'contact_info' in request.data:
            profile.contact_info = (request.data.get('contact_info') or '').strip()
            profile.save(update_fields=['contact_info'])

        return Response({'success': True, 'message': '个人信息已更新', 'data': ProfileSerializer(user).data})


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password') or ''
        new_password = request.data.get('new_password') or ''

        if not old_password or not new_password:
            return Response({'success': False, 'message': '请填写旧密码和新密码'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        if not user.check_password(old_password):
            return Response({'success': False, 'message': '旧密码不正确'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
            security_questions = hash_security_questions(request.data.get('security_questions'))
        except DjangoValidationError as exc:
            return Response({'success': False, 'message': '；'.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user.set_password(new_password)
            user.save(update_fields=['password'])

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.security_questions = security_questions
            profile.has_changed_password = True
            profile.failed_login_attempts = 0
            profile.login_locked_until = None
            profile.login_locked = False
            profile.save(update_fields=[
                'security_questions', 'has_changed_password', 'failed_login_attempts',
                'login_locked_until', 'login_locked',
            ])

        return Response({'success': True, 'message': '密码修改成功，请重新登录'})


def _mask_secret(value):
    text = str(value or '')
    if len(text) <= 8:
        return '*' * len(text)
    return f"{text[:4]}{'*' * (len(text) - 8)}{text[-4:]}"


class DeepSeekConfigAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        api_key = SystemConfig.objects.filter(key='deepseek.api_key').values_list('value', flat=True).first() or ''
        base_url = SystemConfig.objects.filter(key='deepseek.base_url').values_list('value', flat=True).first() or 'https://api.deepseek.com/v1'
        model = SystemConfig.objects.filter(key='deepseek.model').values_list('value', flat=True).first() or 'deepseek-chat'
        temperature = SystemConfig.objects.filter(key='deepseek.temperature').values_list('value', flat=True).first() or '0.3'
        system_prompt = SystemConfig.objects.filter(key='deepseek.system_prompt').values_list('value', flat=True).first() or ''

        return Response(
            {
                'success': True,
                'data': {
                    'has_api_key': bool(str(api_key).strip()),
                    'api_key_masked': _mask_secret(api_key),
                    'base_url': str(base_url),
                    'model': str(model),
                    'temperature': str(temperature),
                    'system_prompt': str(system_prompt),
                },
            }
        )

    def put(self, request):
        denied = _forbid_if_no_write_permission(request, 'system_ai_config', 'update_deepseek_config')
        if denied:
            return denied

        raw_base_url = (request.data.get('base_url') or '').strip()
        raw_model = (request.data.get('model') or '').strip()
        raw_temperature = (request.data.get('temperature') or '').strip()
        raw_system_prompt = (request.data.get('system_prompt') or '').strip()
        raw_api_key = request.data.get('api_key')

        base_url = raw_base_url or 'https://api.deepseek.com/v1'
        model = raw_model or 'deepseek-chat'
        temperature = raw_temperature or '0.3'

        try:
            temp_value = float(temperature)
            if temp_value < 0 or temp_value > 1:
                raise ValueError()
        except ValueError:
            return Response({'success': False, 'message': 'temperature 必须是 0~1 之间的数字'}, status=status.HTTP_400_BAD_REQUEST)

        items = [
            ('deepseek.base_url', base_url, 'string', 'DeepSeek OpenAI 兼容接口地址'),
            ('deepseek.model', model, 'string', 'DeepSeek 模型名称'),
            ('deepseek.temperature', str(temp_value), 'string', 'DeepSeek 温度参数'),
        ]

        if raw_system_prompt:
            items.append(('deepseek.system_prompt', raw_system_prompt, 'text', 'DeepSeek 公文生成系统提示词'))

        for key, value, value_type, remark in items:
            obj, _ = SystemConfig.objects.get_or_create(
                key=key,
                defaults={
                    'value': value,
                    'value_type': value_type,
                    'remark': remark,
                    'is_public': False,
                },
            )
            if obj.value != value:
                obj.value = value
                obj.save(update_fields=['value', 'updated_at'])

        if raw_api_key is not None:
            api_key = str(raw_api_key).strip()
            if api_key:
                obj, _ = SystemConfig.objects.get_or_create(
                    key='deepseek.api_key',
                    defaults={
                        'value': api_key,
                        'value_type': 'string',
                        'remark': 'DeepSeek API Key',
                        'is_public': False,
                    },
                )
                if obj.value != api_key:
                    obj.value = api_key
                    obj.save(update_fields=['value', 'updated_at'])

        _record_operation(request, 'system_ai_config', 'update_deepseek_config', success=True)
        return Response({'success': True, 'message': 'DeepSeek 配置已保存'})


class UserListCreateAPIView(APIView):
    permission_classes = [UserManagementPermission]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        queryset = User.objects.all().order_by('-id')
        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword)
                | Q(first_name__icontains=keyword)
                | Q(last_name__icontains=keyword)
                | Q(email__icontains=keyword)
            )
        rows = UserListSerializer(queryset[:500], many=True).data
        return Response({'success': True, 'rows': rows, 'total': queryset.count()})

    def post(self, request):
        serializer = UserCreateUpdateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not data.get('password'):
            return Response({'success': False, 'message': '创建用户必须设置初始密码'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(data['password'])
            security_questions = hash_security_questions(request.data.get('security_questions'))
        except DjangoValidationError as exc:
            return Response({'success': False, 'message': '；'.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=data['username']).exists():
            return Response({'success': False, 'message': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User.objects.create_user(
                username=data['username'],
                password=data['password'],
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                email=data.get('email', ''),
                is_active=data.get('is_active', True),
                is_staff=data.get('is_staff', True),
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.security_questions = security_questions
            profile.save(update_fields=['security_questions'])
            group_ids = data.get('group_ids') or []
            if group_ids:
                user.groups.set(Group.objects.filter(id__in=group_ids))

        _record_operation(request, 'system_user', 'add_user', detail=f'用户：{user.username}')
        return Response({'success': True, 'message': '用户创建成功', 'data': UserListSerializer(user).data}, status=status.HTTP_201_CREATED)


class UserDetailAPIView(APIView):
    permission_classes = [UserManagementPermission]

    def get_object(self, user_id):
        return User.objects.filter(id=user_id).first()

    def get(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({'success': False, 'message': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True, 'data': UserListSerializer(user).data})

    def patch(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({'success': False, 'message': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserCreateUpdateSerializer(data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        password_security_questions = None
        if data.get('password'):
            try:
                validate_password(data['password'], user=user)
                password_security_questions = hash_security_questions(request.data.get('security_questions'))
            except DjangoValidationError as exc:
                return Response({'success': False, 'message': '；'.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        if 'username' in data and data['username'] != user.username:
            if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response({'success': False, 'message': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)
            user.username = data['username']

        for field in ['first_name', 'last_name', 'email', 'is_active', 'is_staff']:
            if field in data:
                setattr(user, field, data[field])

        if data.get('password'):
            user.set_password(data['password'])

        with transaction.atomic():
            user.save()

            if password_security_questions is not None:
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.security_questions = password_security_questions
                profile.has_changed_password = True
                profile.failed_login_attempts = 0
                profile.login_locked_until = None
                profile.login_locked = False
                profile.save(update_fields=[
                    'security_questions', 'has_changed_password', 'failed_login_attempts',
                    'login_locked_until', 'login_locked',
                ])

            if 'group_ids' in data:
                user.groups.set(Group.objects.filter(id__in=data['group_ids']))

        _record_operation(request, 'system_user', 'change_user', detail=f'用户：{user.username}')
        return Response({'success': True, 'message': '用户更新成功', 'data': UserListSerializer(user).data})

    def delete(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({'success': False, 'message': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        if user.id == request.user.id:
            return Response({'success': False, 'message': '不能删除当前登录用户'}, status=status.HTTP_400_BAD_REQUEST)

        username = user.username
        user.delete()
        _record_operation(request, 'system_user', 'delete_user', detail=f'用户：{username}')
        return Response({'success': True, 'message': '用户已删除'})


def _role_error(message, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message}, status=http_status)


def _validate_role_name(name, exclude_id=None):
    name = (name or '').strip()
    if not name:
        return None, '角色名称不能为空'
    if len(name) > 150:
        return None, '角色名称不能超过150个字符'
    existing = Group.objects.filter(name__iexact=name)
    if exclude_id:
        existing = existing.exclude(id=exclude_id)
    if existing.exists():
        return None, '角色名称已存在'
    return name, None


def _ungrantable_permissions(user, permissions):
    """非超级管理员只能授予自己已拥有的权限，防止通过角色提权。"""
    if _is_super_admin_user(user):
        return []
    return [perm for perm in permissions if not user.has_perm(f'{perm.content_type.app_label}.{perm.codename}')]


class RoleListAPIView(APIView):
    permission_classes = [GroupManagementPermission]

    def get(self, request):
        roles = Group.objects.all().order_by('id')
        return Response({'success': True, 'rows': RoleSerializer(roles, many=True).data})

    def post(self, request):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'create_role')
        if denied:
            return denied

        name, error = _validate_role_name(request.data.get('name'))
        if error:
            return _role_error(error)
        if name in BUILTIN_GROUP_NAMES:
            return _role_error('内置角色名称不可用于自定义角色')

        template_key = (request.data.get('template') or '').strip()
        if template_key and template_key not in ROLE_TEMPLATES:
            return _role_error('角色模板不存在')

        try:
            permission_ids = _validate_id_list(request.data.get('permission_ids'), 'permission_ids')
        except ValueError as exc:
            return _role_error(str(exc))

        if template_key:
            permissions, _missing = resolve_permissions(ROLE_TEMPLATES[template_key]['permissions'])
        else:
            permissions = list(Permission.objects.select_related('content_type').filter(id__in=permission_ids))
            if len(permissions) != len(set(permission_ids)):
                return _role_error('包含不存在的权限条目')

        denied_perms = _ungrantable_permissions(request.user, permissions)
        if denied_perms:
            return _role_error('不能授予自己未拥有的权限', status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            role = Group.objects.create(name=name)
            role.permissions.set(permissions)
            if template_key:
                menu_paths = ROLE_TEMPLATES[template_key].get('menu_paths')
                if menu_paths:
                    for menu in Menu.objects.filter(path__in=menu_paths):
                        menu.roles.add(role)

        _record_operation(request, 'system_role', 'create_role', success=True, detail=f'role_id={role.id}, name={name}, template={template_key}')
        return Response({'success': True, 'message': '角色已创建', 'data': RoleSerializer(role).data}, status=status.HTTP_201_CREATED)


class RoleDetailAPIView(APIView):
    permission_classes = [GroupManagementPermission]

    def patch(self, request, role_id):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'update_role')
        if denied:
            return denied
        role = Group.objects.filter(id=role_id).first()
        if not role:
            return _role_error('角色不存在', status.HTTP_404_NOT_FOUND)
        if is_builtin_group(role):
            return _role_error('内置角色不可重命名')

        name, error = _validate_role_name(request.data.get('name'), exclude_id=role.id)
        if error:
            return _role_error(error)
        if name in BUILTIN_GROUP_NAMES:
            return _role_error('内置角色名称不可用于自定义角色')

        role.name = name
        role.save(update_fields=['name'])
        _record_operation(request, 'system_role', 'update_role', success=True, detail=f'role_id={role.id}, name={name}')
        return Response({'success': True, 'message': '角色已更新', 'data': RoleSerializer(role).data})

    def delete(self, request, role_id):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'delete_role')
        if denied:
            return denied
        role = Group.objects.filter(id=role_id).first()
        if not role:
            return _role_error('角色不存在', status.HTTP_404_NOT_FOUND)
        if is_builtin_group(role):
            return _role_error('内置角色不可删除')
        user_count = role.user_set.count()
        if user_count:
            return _role_error(f'该角色下仍有 {user_count} 名用户，请先移除用户后再删除')

        role_name = role.name
        role.delete()
        _record_operation(request, 'system_role', 'delete_role', success=True, detail=f'role_id={role_id}, name={role_name}')
        return Response({'success': True, 'message': '角色已删除'})


class RoleTemplateListAPIView(APIView):
    permission_classes = [GroupManagementPermission]

    def get(self, request):
        rows = []
        for key, template in ROLE_TEMPLATES.items():
            permissions, _missing = resolve_permissions(template['permissions'])
            rows.append({
                'key': key,
                'label': template['label'],
                'description': template['description'],
                'permission_ids': [perm.id for perm in permissions],
                'permission_count': len(permissions),
            })
        return Response({'success': True, 'rows': rows})


class RoleApplyTemplateAPIView(APIView):
    """把内置模板权限重新写入指定角色（内置角色用于恢复默认权限）。"""
    permission_classes = [GroupManagementPermission]
    template_action = True

    def post(self, request, role_id):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'apply_template')
        if denied:
            return denied
        role = Group.objects.filter(id=role_id).first()
        if not role:
            return _role_error('角色不存在', status.HTTP_404_NOT_FOUND)

        if role.name == '超级管理员':
            if not _is_super_admin_user(request.user):
                return _role_error('仅超级管理员可恢复最高权限用户组', status.HTTP_403_FORBIDDEN)
            role.permissions.set(Permission.objects.all())
            _record_operation(request, 'system_role', 'apply_template', detail=f'用户组：{role.name}')
            return Response({'success': True, 'message': '已恢复超级管理员全部权限', 'data': RoleSerializer(role).data})

        if is_builtin_group(role):
            template_key = role.name
        else:
            template_key = (request.data.get('template') or '').strip()
        if template_key not in ROLE_TEMPLATES:
            return _role_error('角色模板不存在')

        permissions, _missing = resolve_permissions(ROLE_TEMPLATES[template_key]['permissions'])
        if _ungrantable_permissions(request.user, permissions):
            return _role_error('不能授予自己未拥有的权限', status.HTTP_403_FORBIDDEN)

        count, _ = apply_role_template(role, template_key)
        _record_operation(request, 'system_role', 'apply_template', success=True, detail=f'role_id={role.id}, template={template_key}, count={count}')
        return Response({'success': True, 'message': '已应用角色模板', 'data': RoleSerializer(role).data})


class MenuListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        queryset = Menu.objects.all().order_by('order_num', 'id')
        rows = MenuSerializer(queryset, many=True).data
        rows = _filter_menu_rows_for_user(list(rows), request.user)
        return Response({'success': True, 'rows': rows, 'tree': _build_menu_tree(list(rows))})

    def post(self, request):
        denied = _forbid_if_not_super_admin(request, 'system_menu', 'create_menu')
        if denied:
            return denied

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'success': False, 'message': '菜单名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        menu_type = (request.data.get('menu_type') or 'menu').strip()
        if menu_type not in {'directory', 'menu', 'button'}:
            return Response({'success': False, 'message': '菜单类型非法'}, status=status.HTTP_400_BAD_REQUEST)

        parent_id = request.data.get('parent_id')
        parent = None
        if parent_id not in (None, '', 0, '0'):
            parent = Menu.objects.filter(id=parent_id).first()
            if not parent:
                return Response({'success': False, 'message': '父级菜单不存在'}, status=status.HTTP_400_BAD_REQUEST)

        role_ids_raw = request.data.get('role_ids')
        try:
            role_ids = _validate_id_list(role_ids_raw, 'role_ids')
        except ValueError as exc:
            return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        menu = Menu.objects.create(
            name=name,
            path=(request.data.get('path') or '').strip(),
            component=(request.data.get('component') or '').strip(),
            icon=(request.data.get('icon') or '').strip(),
            permission_code=(request.data.get('permission_code') or '').strip(),
            menu_type=menu_type,
            visible=bool(request.data.get('visible', True)),
            keep_alive=bool(request.data.get('keep_alive', False)),
            order_num=int(request.data.get('order_num') or 0),
            is_active=bool(request.data.get('is_active', True)),
            parent=parent,
        )
        if role_ids:
            menu.roles.set(Group.objects.filter(id__in=role_ids))

        _record_operation(request, 'system_menu', 'create_menu', success=True, detail=f'menu_id={menu.id}')
        return Response({'success': True, 'message': '菜单创建成功', 'data': MenuSerializer(menu).data}, status=status.HTTP_201_CREATED)


class MenuDetailAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get_object(self, menu_id):
        return Menu.objects.filter(id=menu_id).first()

    def patch(self, request, menu_id):
        denied = _forbid_if_not_super_admin(request, 'system_menu', 'update_menu')
        if denied:
            return denied

        menu = self.get_object(menu_id)
        if not menu:
            return Response({'success': False, 'message': '菜单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if 'name' in request.data:
            name = (request.data.get('name') or '').strip()
            if not name:
                return Response({'success': False, 'message': '菜单名称不能为空'}, status=status.HTTP_400_BAD_REQUEST)
            menu.name = name

        if 'menu_type' in request.data:
            menu_type = (request.data.get('menu_type') or '').strip()
            if menu_type not in {'directory', 'menu', 'button'}:
                return Response({'success': False, 'message': '菜单类型非法'}, status=status.HTTP_400_BAD_REQUEST)
            menu.menu_type = menu_type

        for field in ['path', 'component', 'icon', 'permission_code']:
            if field in request.data:
                setattr(menu, field, (request.data.get(field) or '').strip())

        for field in ['visible', 'keep_alive', 'is_active']:
            if field in request.data:
                setattr(menu, field, bool(request.data.get(field)))

        if 'order_num' in request.data:
            try:
                menu.order_num = int(request.data.get('order_num') or 0)
            except (TypeError, ValueError):
                return Response({'success': False, 'message': '排序值非法'}, status=status.HTTP_400_BAD_REQUEST)

        if 'parent_id' in request.data:
            parent_id = request.data.get('parent_id')
            if parent_id in (None, '', 0, '0'):
                menu.parent = None
            else:
                parent = Menu.objects.filter(id=parent_id).first()
                if not parent:
                    return Response({'success': False, 'message': '父级菜单不存在'}, status=status.HTTP_400_BAD_REQUEST)
                if parent.id == menu.id:
                    return Response({'success': False, 'message': '父级菜单不能指向自身'}, status=status.HTTP_400_BAD_REQUEST)
                menu.parent = parent

        if 'role_ids' in request.data:
            try:
                role_ids = _validate_id_list(request.data.get('role_ids'), 'role_ids')
            except ValueError as exc:
                return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            menu.roles.set(Group.objects.filter(id__in=role_ids))

        menu.save()
        _record_operation(request, 'system_menu', 'update_menu', success=True, detail=f'menu_id={menu.id}')
        return Response({'success': True, 'message': '菜单更新成功', 'data': MenuSerializer(menu).data})

    def delete(self, request, menu_id):
        denied = _forbid_if_not_super_admin(request, 'system_menu', 'delete_menu')
        if denied:
            return denied

        menu = self.get_object(menu_id)
        if not menu:
            return Response({'success': False, 'message': '菜单不存在'}, status=status.HTTP_404_NOT_FOUND)

        if menu.children.exists():
            return Response({'success': False, 'message': '请先删除子菜单'}, status=status.HTTP_400_BAD_REQUEST)

        menu.delete()
        _record_operation(request, 'system_menu', 'delete_menu', success=True, detail=f'menu_id={menu_id}')
        return Response({'success': True, 'message': '菜单已删除'})


class RolePermissionAPIView(APIView):
    permission_classes = [GroupManagementPermission]

    def get_role(self, role_id):
        return Group.objects.filter(id=role_id).first()

    def get(self, request, role_id):
        role = self.get_role(role_id)
        if not role:
            return Response({'success': False, 'message': '角色不存在'}, status=status.HTTP_404_NOT_FOUND)

        permissions = role.permissions.select_related('content_type').all().order_by('content_type__app_label', 'codename')
        return Response(
            {
                'success': True,
                'data': {
                    'role_id': role.id,
                    'role_name': role.name,
                    'permission_ids': list(permissions.values_list('id', flat=True)),
                    'rows': PermissionSerializer(permissions, many=True, context={'user': request.user}).data,
                },
            }
        )

    def put(self, request, role_id):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'assign_permissions')
        if denied:
            return denied

        role = self.get_role(role_id)
        if not role:
            return Response({'success': False, 'message': '角色不存在'}, status=status.HTTP_404_NOT_FOUND)

        try:
            permission_ids = _validate_id_list(request.data.get('permission_ids'), 'permission_ids')
        except ValueError as exc:
            return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if is_builtin_group(role):
            return Response({'success': False, 'message': '内置角色权限由模板维护，不可手动修改，可使用“恢复模板权限”'}, status=status.HTTP_400_BAD_REQUEST)

        permissions = list(Permission.objects.select_related('content_type').filter(id__in=permission_ids))
        if len(permissions) != len(set(permission_ids)):
            return _role_error('包含不存在的权限条目')
        if _ungrantable_permissions(request.user, permissions):
            return Response({'success': False, 'message': '不能授予自己未拥有的权限'}, status=status.HTTP_403_FORBIDDEN)

        role.permissions.set(permissions)
        _record_operation(request, 'system_role', 'assign_permissions', success=True, detail=f'role_id={role.id}, count={len(permission_ids)}')
        return Response({'success': True, 'message': '角色权限已更新'})


class RoleMenuAPIView(APIView):
    permission_classes = [GroupManagementPermission]

    def get_role(self, role_id):
        return Group.objects.filter(id=role_id).first()

    def get(self, request, role_id):
        role = self.get_role(role_id)
        if not role:
            return Response({'success': False, 'message': '角色不存在'}, status=status.HTTP_404_NOT_FOUND)

        menus = role.system_menus.all().order_by('order_num', 'id')
        rows = MenuSerializer(menus, many=True).data
        return Response(
            {
                'success': True,
                'data': {
                    'role_id': role.id,
                    'role_name': role.name,
                    'menu_ids': list(menus.values_list('id', flat=True)),
                    'rows': rows,
                    'tree': _build_menu_tree(list(rows)),
                },
            }
        )

    def put(self, request, role_id):
        denied = _forbid_if_no_write_permission(request, 'system_role', 'assign_menus')
        if denied:
            return denied

        role = self.get_role(role_id)
        if not role:
            return Response({'success': False, 'message': '角色不存在'}, status=status.HTTP_404_NOT_FOUND)

        try:
            menu_ids = _validate_id_list(request.data.get('menu_ids'), 'menu_ids')
        except ValueError as exc:
            return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        role.system_menus.set(Menu.objects.filter(id__in=menu_ids))
        _record_operation(request, 'system_role', 'assign_menus', success=True, detail=f'role_id={role.id}, count={len(menu_ids)}')
        return Response({'success': True, 'message': '角色菜单已更新'})
