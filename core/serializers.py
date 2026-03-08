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
    class Meta:
        model = InspectionRecord
        fields = '__all__'
        read_only_fields = ('inspector',)
