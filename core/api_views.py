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

        nearby_sites_with_distance = []
        for site in HeritageSite.objects.all():
            if site.latitude and site.longitude:
                site_location = (site.latitude, site.longitude)
                distance = geodesic(user_location, site_location).km
                if distance <= radius:
                    nearby_sites_with_distance.append({
                        'site': site,
                        'distance': distance
                    })
        
        # 按距离排序
        nearby_sites_with_distance.sort(key=lambda x: x['distance'])
        
        # 获取序列化数据并附加距离信息
        result = []
        for item in nearby_sites_with_distance:
            site_data = HeritageSerializer(item['site']).data
            site_data['distance'] = round(item['distance'], 2)  # 约到小数点后两位
            result.append(site_data)
        
        return Response(result)

class InspectionViewSet(viewsets.ModelViewSet):
    queryset = InspectionRecord.objects.all()
    serializer_class = InspectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InspectionRecord.objects.filter(inspector=self.request.user).order_by('-inspect_time')

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_records(self, request):
        """获取当前用户的巡查记录，支持分页"""
        queryset = self.get_queryset()
        
        # 分页处理
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 20)
        try:
            page = int(page)
            page_size = int(page_size)
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 20
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        start = (page - 1) * page_size
        end = start + page_size
        records = queryset[start:end]
        
        serializer = self.get_serializer(records, many=True)
        
        # 返回带分页信息的响应
        return Response({
            'count': queryset.count(),
            'page': page,
            'page_size': page_size,
            'results': serializer.data
        })
