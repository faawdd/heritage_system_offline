import json
from django.conf import settings
from .models import HeritageSite


def system_version_context(request):
    """为模板提供动态系统版本号。"""
    updated_at = getattr(settings, 'SYS_VERSION_UPDATED_AT', None)
    updated_at_label = updated_at.strftime('%Y-%m-%d %H:%M') if updated_at else ''
    sys_version = getattr(settings, 'SYS_VERSION', 'v4.0-BuildUnknown')

    return {
        'SYS_VERSION': sys_version,
        'SYS_VERSION_SOURCE': getattr(settings, 'SYS_VERSION_SOURCE', 'unknown'),
        'SYS_VERSION_UPDATED_AT': updated_at_label,
        'APP_VERSION': sys_version,
        'APP_VERSION_STRING': sys_version,
        'APP_VERSION_NAME': '基于最后更新时间自动生成',
        'APP_RELEASE_DATE': updated_at_label,
    }


def heritage_map_context(request):
    if request.path == '/admin/':
        sites = HeritageSite.objects.exclude(longitude__isnull=True).exclude(latitude__isnull=True)
        heritage_list = []
        for s in sites:
            heritage_list.append({
                'name': s.name,
                'lng': float(s.longitude),
                'lat': float(s.latitude)
            })
        
        # 预先生成好要在首页执行的 JavaScript 注入代码
        map_html = """
        <div id='map-box' style='width:100%; height:500px; margin-bottom:20px; border-radius:8px; border:1px solid #ddd;'></div>
        <script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>
        <link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css' />
        """
        
        return {
            'heritage_json': json.dumps(heritage_list),
            'map_injection': map_html
        }
    return {}