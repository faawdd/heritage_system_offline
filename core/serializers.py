from rest_framework import serializers
from core.models import HeritageSite, InspectionRecord
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

class HeritageSerializer(serializers.ModelSerializer):
    distance = serializers.FloatField(read_only=True, required=False, allow_null=True)
    
    class Meta:
        model = HeritageSite
        fields = '__all__'

class InspectionSerializer(serializers.ModelSerializer):
    """
    巡查记录序列化器
    
    支持的字段：
    - site: 文物点ID（必填）
    - is_normal: 是否正常（必填）
    - issue_details: 问题描述（可选）
    - photo: 照片文件（可选）
    - latitude: 巡查纬度（可选）
    - longitude: 巡查经度（可选）
    - inspect_time: 巡查时间（自动设置）
    - inspector: 巡查员（自动设置为当前用户，只读）
    """
    
    class Meta:
        model = InspectionRecord
        fields = ['id', 'site', 'inspector', 'inspect_time', 'is_normal', 'issue_details', 'photo', 'latitude', 'longitude']
        read_only_fields = ('inspector', 'inspect_time', 'id')
        extra_kwargs = {
            'photo': {'required': False, 'allow_null': True},
            'issue_details': {'required': False, 'allow_null': True},
            'latitude': {'required': False, 'allow_null': True},
            'longitude': {'required': False, 'allow_null': True},
        }
