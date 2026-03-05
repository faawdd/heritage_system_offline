import json
from .models import HeritageSite
from heritage_system.version import VERSION, get_version_string


def version_context(request):
    """为模板提供版本号信息"""
    return {
        'APP_VERSION': VERSION['version'],
        'APP_VERSION_STRING': get_version_string(),
        'APP_VERSION_NAME': VERSION['version_name'],
        'APP_RELEASE_DATE': VERSION['release_date'],
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