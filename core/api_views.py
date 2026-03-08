from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from core.models import HeritageSite, InspectionRecord
from django.contrib.auth.models import User
from .serializers import HeritageSerializer, InspectionSerializer, UserSerializer

class AuthViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return Response(UserSerializer(user).data)
        return Response({'error': 'Invalid Credentials'}, status=400)

class HeritageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HeritageSite.objects.all()
    serializer_class = HeritageSerializer
    permission_classes = [permissions.IsAuthenticated]

class InspectionViewSet(viewsets.ModelViewSet):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InspectionRecord.objects.filter(inspector=self.request.user)

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)
