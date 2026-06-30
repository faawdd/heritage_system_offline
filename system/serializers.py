from django.contrib.auth.models import Group, Permission, User
from rest_framework import serializers

from core.models import UserProfile
from system.models import DictionaryItem, DictionaryType, LoginLog, Menu, OperationLog, SystemConfig


class MenuSerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(source='parent.id', read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(source='roles', many=True, read_only=True)

    class Meta:
        model = Menu
        fields = [
            'id',
            'name',
            'path',
            'component',
            'icon',
            'permission_code',
            'menu_type',
            'visible',
            'keep_alive',
            'order_num',
            'is_active',
            'parent_id',
            'role_ids',
        ]


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type_id']


class RoleSerializer(serializers.ModelSerializer):
    permission_count = serializers.IntegerField(source='permissions.count', read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'permission_count']


class UserListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    is_super_admin = serializers.BooleanField(source='is_superuser', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'is_active',
            'is_staff',
            'is_super_admin',
            'date_joined',
            'last_login',
            'roles',
        ]

    def get_roles(self, obj):
        return list(obj.groups.values_list('name', flat=True))


class UserCreateUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_staff = serializers.BooleanField(required=False)
    group_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class ProfileSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'is_staff',
            'is_superuser',
            'roles',
            'profile',
        ]

    def get_roles(self, obj):
        return list(obj.groups.values_list('name', flat=True))

    def get_profile(self, obj):
        profile = UserProfile.objects.filter(user=obj).first()
        if not profile:
            return None
        return {
            'has_changed_password': profile.has_changed_password,
            'first_login_at': profile.first_login_at,
            'contact_info': profile.contact_info,
        }


class LoginLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginLog
        fields = ['id', 'username', 'success', 'ip', 'user_agent', 'message', 'created_at']


class OperationLogSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = OperationLog
        fields = ['id', 'operator_name', 'module', 'action', 'method', 'request_path', 'ip', 'success', 'detail', 'created_at']


class DictionaryTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DictionaryType
        fields = ['id', 'code', 'name', 'remark', 'is_active', 'created_at', 'updated_at']


class DictionaryItemSerializer(serializers.ModelSerializer):
    dict_type_code = serializers.CharField(source='dict_type.code', read_only=True)

    class Meta:
        model = DictionaryItem
        fields = ['id', 'dict_type', 'dict_type_code', 'label', 'value', 'order_num', 'is_default', 'is_active', 'remark', 'created_at', 'updated_at']


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ['id', 'key', 'value', 'value_type', 'remark', 'is_public', 'created_at', 'updated_at']
