"""
URL configuration for heritage_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import (heritage_map_view, heritage_dashboard_view, heritage_stats_api, 
                        heritage_stats_by_category_api, admin_index_view,
                        kanerjing_list_view, kanerjing_stats_api, kanerjing_import_check_view,
                        CustomPasswordChangeDoneView, inspection_mobile_add_view, 
                        inspection_mobile_list_view, export_doc_view, kml_overlay_check_view,
                        ovkml_converter_view, heritage_classification_stats_api, heritage_detail_view,
                        system_version_api)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/home/', admin_index_view, name='admin_home'),  # 自定义首页
    path('admin/heritage/<int:pk>/detail/', heritage_detail_view, name='heritage_detail'),  # 文物详情页（只读）
    path('admin/export_doc/', export_doc_view, name='admin_export_doc'),
    path('admin/ovkml-converter/', ovkml_converter_view, name='ovkml_converter'),
    path('admin/heritage-map/', heritage_map_view, name='heritage_map'),
    path('admin/kml-overlay-check/', kml_overlay_check_view, name='kml_overlay_check'),
    path('admin/heritage-dashboard/', heritage_dashboard_view, name='heritage_dashboard'),
    path('admin/kanerjing/', kanerjing_list_view, name='kanerjing_list'),  # 坎儿井专项管理
    path('admin/kanerjing-import-check/', kanerjing_import_check_view, name='kanerjing_import_check'),  # 导入检查
    path('admin/password_change/done/', CustomPasswordChangeDoneView.as_view(), name='admin_password_change_done'),  # 自定义密码修改完成
    # 手机端优化页面
    path('mobile/add/', inspection_mobile_add_view, name='inspection_mobile_add'),  # 手机版添加巡查
    path('mobile/list/', inspection_mobile_list_view, name='inspection_mobile_list'),  # 手机版列表
    path('api/heritage-stats/', heritage_stats_api, name='heritage_stats_api'),
    path('api/heritage-stats-by-category/', heritage_stats_by_category_api, name='heritage_stats_by_category_api'),
    path('api/heritage-classification-stats/', heritage_classification_stats_api, name='heritage_classification_stats_api'),
    path('api/kanerjing-stats/', kanerjing_stats_api, name='kanerjing_stats_api'),  # 坎儿井统计API
    path('api/system-version/', system_version_api, name='system_version_api'),  # 系统版本号API
    path('api/', include('core.api_urls')), # API for Flutter App
    path('admin/', admin.site.urls),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)