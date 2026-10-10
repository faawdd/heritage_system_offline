from django.contrib.auth.models import Permission, User
from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from system.admin_access import PermissionCatalogPermission, UserManagementPermission, is_system_superuser, management_capabilities
from system.models import OperationLog
from system.serializers import PermissionSerializer


class UserPermissionInput(serializers.Serializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.select_related('content_type'), many=True,
    )


class UserPermissionAPIView(APIView):
    permission_classes = [UserManagementPermission]

    def get(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'success': False, 'message': '用户不存在'}, status=404)
        return Response({'success': True, 'data': {
            'user_id': user.pk, 'username': user.username,
            'permission_ids': list(user.user_permissions.values_list('pk', flat=True)),
            'group_permission_ids': list(Permission.objects.filter(group__user=user).values_list('pk', flat=True).distinct()),
            'effective_permissions': sorted(user.get_all_permissions()),
            'is_super_admin': is_system_superuser(user),
        }})

    def put(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            return Response({'success': False, 'message': '用户不存在'}, status=404)
        serializer = UserPermissionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        permissions = serializer.validated_data['permission_ids']
        if not is_system_superuser(request.user) and any(
            not request.user.has_perm(f'{perm.content_type.app_label}.{perm.codename}') for perm in permissions
        ):
            return Response({'success': False, 'message': '不能授予自己未拥有的权限'}, status=403)
        with transaction.atomic():
            user.user_permissions.set(permissions)
            OperationLog.objects.create(
                operator=request.user, module='system_user', action='assign_user_permissions',
                method=request.method, request_path=request.path,
                detail=f'用户：{user.username}；直接权限数量：{len(permissions)}', success=True,
            )
        return Response({'success': True, 'message': '用户直接权限已更新，用户组继承权限不受影响'})


class PermissionCatalogAPIView(APIView):
    permission_classes = [PermissionCatalogPermission]

    def get(self, request):
        queryset = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')
        return Response({
            'success': True, 'rows': PermissionSerializer(queryset, many=True, context={'user': request.user}).data,
            'capabilities': management_capabilities(request.user),
        })
