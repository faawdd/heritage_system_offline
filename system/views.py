from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from core.permission_decorators import can_modify_core_data
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from core.models import UserProfile
from core.permissions.api_permissions import IsManagementAdmin
from system.models import LoginLog, Menu, OperationLog
from system.serializers import (
    LoginLogSerializer,
    MenuSerializer,
    OperationLogSerializer,
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
    if can_modify_core_data(request.user):
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

        user = authenticate(request, username=username, password=password)
        if not user:
            LoginLog.objects.create(username=username, success=False, ip=ip, user_agent=user_agent, message='用户名或密码错误')
            return Response({'success': False, 'message': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            LoginLog.objects.create(username=username, user=user, success=False, ip=ip, user_agent=user_agent, message='用户已禁用')
            return Response({'success': False, 'message': '用户已禁用'}, status=status.HTTP_403_FORBIDDEN)

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


class SystemAdminEntryAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def post(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({'success': False, 'message': '未登录'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'success': False, 'message': '用户已禁用'}, status=status.HTTP_403_FORBIDDEN)

        if not (user.is_staff or user.is_superuser):
            return Response({'success': False, 'message': '当前账号无权进入后台管理'}, status=status.HTTP_403_FORBIDDEN)

        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session['admin_sso_from_vue'] = True

        return Response(
            {
                'success': True,
                'data': {
                    'redirect_url': '/admin/home/',
                },
            }
        )


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

        user.set_password(new_password)
        user.save(update_fields=['password'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.has_changed_password = True
        profile.save(update_fields=['has_changed_password'])

        return Response({'success': True, 'message': '密码修改成功，请重新登录'})


class UserListCreateAPIView(APIView):
    permission_classes = [IsManagementAdmin]

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
        serializer = UserCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if User.objects.filter(username=data['username']).exists():
            return Response({'success': False, 'message': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=data['username'],
            password=(data.get('password') or '123456'),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email', ''),
            is_active=data.get('is_active', True),
            is_staff=data.get('is_staff', True),
        )
        group_ids = data.get('group_ids') or []
        if group_ids:
            user.groups.set(Group.objects.filter(id__in=group_ids))

        return Response({'success': True, 'message': '用户创建成功', 'data': UserListSerializer(user).data}, status=status.HTTP_201_CREATED)


class UserDetailAPIView(APIView):
    permission_classes = [IsManagementAdmin]

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

        serializer = UserCreateUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'username' in data and data['username'] != user.username:
            if User.objects.filter(username=data['username']).exclude(id=user.id).exists():
                return Response({'success': False, 'message': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)
            user.username = data['username']

        for field in ['first_name', 'last_name', 'email', 'is_active', 'is_staff']:
            if field in data:
                setattr(user, field, data[field])

        if data.get('password'):
            user.set_password(data['password'])

        user.save()

        if 'group_ids' in data:
            user.groups.set(Group.objects.filter(id__in=data['group_ids']))

        return Response({'success': True, 'message': '用户更新成功', 'data': UserListSerializer(user).data})

    def delete(self, request, user_id):
        user = self.get_object(user_id)
        if not user:
            return Response({'success': False, 'message': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        if user.id == request.user.id:
            return Response({'success': False, 'message': '不能删除当前登录用户'}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({'success': True, 'message': '用户已删除'})


class RoleListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        roles = Group.objects.all().order_by('id')
        return Response({'success': True, 'rows': RoleSerializer(roles, many=True).data})


class PermissionListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        queryset = Permission.objects.select_related('content_type').all().order_by('content_type__app_label', 'codename')
        return Response({'success': True, 'rows': PermissionSerializer(queryset, many=True).data})


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
    permission_classes = [IsManagementAdmin]

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
                    'rows': PermissionSerializer(permissions, many=True).data,
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

        role.permissions.set(Permission.objects.filter(id__in=permission_ids))
        _record_operation(request, 'system_role', 'assign_permissions', success=True, detail=f'role_id={role.id}, count={len(permission_ids)}')
        return Response({'success': True, 'message': '角色权限已更新'})


class RoleMenuAPIView(APIView):
    permission_classes = [IsManagementAdmin]

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


class LoginLogListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        success = (request.GET.get('success') or '').strip().lower()
        page = max(int(request.GET.get('page', 1) or 1), 1)
        page_size = min(max(int(request.GET.get('page_size', 20) or 20), 1), 100)

        queryset = LoginLog.objects.select_related('user').all().order_by('-created_at')
        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword)
                | Q(ip__icontains=keyword)
                | Q(message__icontains=keyword)
            )

        if success in {'1', 'true', 'yes'}:
            queryset = queryset.filter(success=True)
        elif success in {'0', 'false', 'no'}:
            queryset = queryset.filter(success=False)

        total = queryset.count()
        offset = (page - 1) * page_size
        rows = LoginLogSerializer(queryset[offset: offset + page_size], many=True).data

        return Response(
            {
                'success': True,
                'rows': rows,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                },
            }
        )


class OperationLogListAPIView(APIView):
    permission_classes = [IsManagementAdmin]

    def get(self, request):
        keyword = (request.GET.get('keyword') or '').strip()
        success = (request.GET.get('success') or '').strip().lower()
        module = (request.GET.get('module') or '').strip()
        action = (request.GET.get('action') or '').strip()
        page = max(int(request.GET.get('page', 1) or 1), 1)
        page_size = min(max(int(request.GET.get('page_size', 20) or 20), 1), 100)

        queryset = OperationLog.objects.select_related('operator').all().order_by('-created_at')
        if keyword:
            queryset = queryset.filter(
                Q(module__icontains=keyword)
                | Q(action__icontains=keyword)
                | Q(request_path__icontains=keyword)
                | Q(detail__icontains=keyword)
                | Q(operator__username__icontains=keyword)
            )
        if module:
            queryset = queryset.filter(module__icontains=module)
        if action:
            queryset = queryset.filter(action__icontains=action)
        if success in {'1', 'true', 'yes'}:
            queryset = queryset.filter(success=True)
        elif success in {'0', 'false', 'no'}:
            queryset = queryset.filter(success=False)

        total = queryset.count()
        offset = (page - 1) * page_size
        rows = OperationLogSerializer(queryset[offset: offset + page_size], many=True).data

        return Response(
            {
                'success': True,
                'rows': rows,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                },
            }
        )
