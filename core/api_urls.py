from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core import api_views

router = DefaultRouter()
router.register(r'auth', api_views.AuthViewSet, basename='auth')
router.register(r'heritages', api_views.HeritageViewSet)
router.register(r'inspections', api_views.InspectionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
