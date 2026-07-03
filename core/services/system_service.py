from django.conf import settings

from heritage_system.version import VERSION_HISTORY


def get_system_version_payload():
    version_string = getattr(settings, 'SYS_VERSION', 'v1.0+19700101.0000')
    system_name = getattr(settings, 'SYSTEM_NAME', '文物管理系统（离线版）')
    return {
        'system_name': system_name,
        'version': version_string,
        'version_history': VERSION_HISTORY,
    }
