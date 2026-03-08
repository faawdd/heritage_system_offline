from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from geopy.distance import geodesic
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
            refresh = RefreshToken.for_user(user)
            return Response({
                'token': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        return Response({'error': 'Invalid Credentials'}, status=400)

class HeritageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HeritageSite.objects.all()
    serializer_class = HeritageSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def nearby(self, request):
        lat = request.query_params.get('latitude')
        lon = request.query_params.get('longitude')
        radius = request.query_params.get('radius', 5) # 默认5公里

        if not lat or not lon:
            return Response({'error': 'Latitude and longitude are required.'}, status=400)

        try:
            user_location = (float(lat), float(lon))
            radius = float(radius)
        except (ValueError, TypeError):
            return Response({'error': 'Invalid latitude, longitude, or radius.'}, status=400)

        nearby_sites = []
        for site in HeritageSite.objects.all():
            if site.latitude and site.longitude:
                site_location = (site.latitude, site.longitude)
                distance = geodesic(user_location, site_location).km
                if distance <= radius:
                    nearby_sites.append(site)
        
        serializer = self.get_serializer(nearby_sites, many=True)
        return Response(serializer.data)

class InspectionViewSet(viewsets.ModelViewSet):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InspectionRecord.objects.filter(inspector=self.request.user)

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)
