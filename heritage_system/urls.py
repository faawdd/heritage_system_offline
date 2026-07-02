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
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core.views import (heritage_map_view, heritage_dashboard_view, heritage_stats_api,
                        heritage_stats_by_category_api, admin_index_view,
                        admin_direct_entry_block_view,
                        kanerjing_list_view, kanerjing_stats_api, kanerjing_import_check_view,
                        CustomPasswordChangeDoneView, inspection_mobile_add_view,
                        inspection_mobile_list_view, kml_overlay_check_view,
                        ovkml_converter_view, kml_process_convert_view,
                        heritage_classification_stats_api, heritage_detail_view,
                        heritage_boundary_export_view,
                        mobile_kml_entry_view, mobile_collect_entry_view, app_showcase_view,
                        system_version_api, heritage_collect_view,
                        dem_elevation_lookup_api,
                        heritage_detail_preview_view,
                        export_immovable_heritage_docx_view,
                        land_project_management_view, land_project_edit_view,
                        land_project_list_api, land_project_detail_api,
                        land_project_create_api, land_project_upload_api,
                        land_project_download_misc_zip_api,
                        verify_project_spatial_safety_api, land_project_next_doc_num_api,
                        land_project_workflow_action_api, land_project_controls_api)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('', RedirectView.as_view(url='/static/frontend/', permanent=False), name='root_to_vue'),
    path('api/v1/', include('core.api.urls')),
    path('api/v1/system/', include('system.urls')),
    # 兼容旧项目管理入口，统一跳转到新重构页面
    re_path(r'^admin/core/projectaudit(?:/.*)?$', RedirectView.as_view(url='/admin/land-projects/', permanent=False, query_string=True), name='projectaudit_legacy_redirect'),
    path('app-download/', app_showcase_view, name='app_showcase'),
    path('download/', app_showcase_view, name='app_showcase_alias'),
    path('mobile/collect/', heritage_collect_view, name='heritage_collect'),  # 鄯善县不可移动文物采集
    path('mobile/collect/<int:pk>/preview/', heritage_detail_preview_view, name='heritage_detail_preview'),  # 采集登记表预览
    path('mobile/collect/<int:pk>/export-docx/', export_immovable_heritage_docx_view, name='export_immovable_heritage_docx'),
    path('admin/home/', admin_index_view, name='admin_home'),  # 自定义首页
    path('admin/heritage/<int:pk>/detail/', heritage_detail_view, name='heritage_detail'),  # 文物详情页（只读）
    path('admin/heritage/<int:pk>/boundary-export/', heritage_boundary_export_view, name='heritage_boundary_export'),
    path('admin/ovkml-converter/', ovkml_converter_view, name='ovkml_converter'),
    path('admin/kml-process-convert/', kml_process_convert_view, name='kml_process_convert'),
    path('admin/land-projects/', land_project_management_view, name='land_project_management'),
    path('admin/land-projects/edit/', land_project_edit_view, name='land_project_edit'),
    path('admin/heritage-map/', heritage_map_view, name='heritage_map'),
    path('admin/kml-overlay-check/', kml_overlay_check_view, name='kml_overlay_check'),
    path('admin/kml-management/', RedirectView.as_view(pattern_name='kml_overlay_check', permanent=True, query_string=True), name='kml_management_alias'),
    path('admin/heritage-dashboard/', heritage_dashboard_view, name='heritage_dashboard'),
    path('admin/kanerjing/', kanerjing_list_view, name='kanerjing_list'),  # 坎儿井专项管理
    path('admin/kanerjing-import-check/', kanerjing_import_check_view, name='kanerjing_import_check'),  # 导入检查
    path('admin/password_change/done/', CustomPasswordChangeDoneView.as_view(), name='admin_password_change_done'),  # 自定义密码修改完成
    # 手机端优化页面
    path('mobile/add/', inspection_mobile_add_view, name='inspection_mobile_add'),  # 手机版添加巡查
    path('mobile/list/', inspection_mobile_list_view, name='inspection_mobile_list'),  # 手机版列表
    path('mobile/kml-entry/', mobile_kml_entry_view, name='mobile_kml_entry'),
    path('mobile/collect-entry/', mobile_collect_entry_view, name='mobile_collect_entry'),
    path('api/heritage-stats/', heritage_stats_api, name='heritage_stats_api'),
    path('api/heritage-stats-by-category/', heritage_stats_by_category_api, name='heritage_stats_by_category_api'),
    path('api/heritage-classification-stats/', heritage_classification_stats_api, name='heritage_classification_stats_api'),
    path('api/kanerjing-stats/', kanerjing_stats_api, name='kanerjing_stats_api'),  # 坎儿井统计API
    path('api/dem-elevation-lookup/', dem_elevation_lookup_api, name='dem_elevation_lookup_api'),
    path('api/system-version/', system_version_api, name='system_version_api'),  # 系统版本号API
    path('api/land-projects/', land_project_list_api, name='land_project_list_api'),
    path('api/land-projects/<uuid:project_id>/', land_project_detail_api, name='land_project_detail_api'),
    path('api/land-projects/create/', land_project_create_api, name='land_project_create_api'),
    path('api/land-projects/<uuid:project_id>/upload/', land_project_upload_api, name='land_project_upload_api'),
    path('api/land-projects/<uuid:project_id>/download-misc-zip/', land_project_download_misc_zip_api, name='land_project_download_misc_zip_api'),
    path('api/land-projects/<uuid:project_id>/verify-spatial-safety/', verify_project_spatial_safety_api, name='verify_project_spatial_safety_api'),
    path('api/land-projects/next-shanshan-doc/', land_project_next_doc_num_api, name='land_project_next_doc_num_api'),
    path('api/land-projects/<uuid:project_id>/workflow-action/', land_project_workflow_action_api, name='land_project_workflow_action_api'),
    path('api/land-projects/<uuid:project_id>/controls/', land_project_controls_api, name='land_project_controls_api'),
    path('admin/login/', admin_direct_entry_block_view, name='admin_login_block'),
    path('admin/', admin_direct_entry_block_view, name='admin_direct_block'),
    path('admin/', admin.site.urls),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)