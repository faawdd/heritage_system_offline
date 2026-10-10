from django.conf import settings

from heritage_system.version import VERSION_HISTORY
from core.models import ImmovableHeritage


def get_system_version_payload():
    version_string = getattr(settings, 'SYS_VERSION', 'v1.0+19700101.0000')
    system_name = getattr(settings, 'SYSTEM_NAME', '文物综合管理平台')
    return {
        'system_name': system_name,
        'version': version_string,
        'version_history': VERSION_HISTORY,
    }


def collection_region_defaults():
    """Only infer a region when imported records agree on one complete hierarchy."""
    regions = list(
        ImmovableHeritage.objects.exclude(sipu_id__isnull=True).exclude(sipu_id='')
        .order_by().values_list('province', 'city', 'county').distinct()[:2]
    )
    if len(regions) == 1 and all(regions[0]):
        return dict(zip(('province', 'city', 'county'), regions[0]))
    return {'province': '', 'city': '', 'county': ''}
