import json
import re

from core.models import HeritageSite, InspectionRecord
from core.services.heritage_inference import parse_address


TOWNSHIP_NORMALIZATION_RULES = [
    ('东巴扎回族乡', '东巴扎回族乡'),
    ('东巴扎乡', '东巴扎回族乡'),
    ('火车站镇', '火车站镇'),
    ('吐峪沟乡', '吐峪沟乡'),
    ('吐峪沟镇', '吐峪沟乡'),
    ('七克台镇', '七克台镇'),
    ('七克台乡', '七克台镇'),
    ('七台镇', '七克台镇'),
    ('连木沁镇', '连木沁镇'),
    ('连木沁乡', '连木沁镇'),
    ('达朗坎乡', '达朗坎乡'),
    ('达浪坎乡', '达朗坎乡'),
    ('鲁克沁镇', '鲁克沁镇'),
    ('辟展镇', '辟展镇'),
    ('辟展乡', '辟展镇'),
    ('鄯善镇', '鄯善镇'),
    ('迪坎镇', '迪坎镇'),
    ('迪坎乡', '迪坎镇'),
]


def normalize_township_name(name):
    text = re.sub(r'\s+', '', str(name or ''))
    aliases = dict(TOWNSHIP_NORMALIZATION_RULES)
    # 旧地址有“鄯善县东北七克台镇”等方位前缀，不属于乡镇名称。
    without_direction = re.sub(r'^(?:东北|东南|西北|西南|东|南|西|北)', '', text)
    if text not in aliases and without_direction in aliases:
        text = without_direction
    return aliases.get(text, text)


def _extract_township_name(address, region_names=()):
    return normalize_township_name(parse_address(address, region_names)['township'])


def site_township(site):
    registration = site.registration
    if registration and registration.township.strip():
        return normalize_township_name(registration.township)
    region_names = [registration.province, registration.city, registration.county] if registration else []
    return _extract_township_name(site.address, region_names)


def _parse_zone(zone_text):
    if not zone_text:
        return []
    try:
        value = json.loads(zone_text)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def get_heritage_map_points():
    rows = []
    for site in HeritageSite.objects.all().only(
        'id', 'registration_id', 'name', 'longitude', 'latitude', 'level',
        'body_boundary', 'protection_zone', 'control_zone'
    ):
        try:
            lng = float(site.longitude)
            lat = float(site.latitude)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                'id': site.id,
                'registration_id': site.registration_id,
                'name': site.name,
                'lng': lng,
                'lat': lat,
                'level': site.level,
                'level_label': site.get_level_display(),
                # 本体边界环列表（[[[lon,lat],...],...]），供前端放大后渲染实际边界范围。
                'body_boundary': _parse_zone(site.body_boundary),
                'protection_zone': _parse_zone(site.protection_zone),
                'control_zone': _parse_zone(site.control_zone),
            }
        )
    return rows


def get_heritage_stats_meta():
    township_counter = {}
    for site in HeritageSite.objects.select_related('registration').all():
        township_name = site_township(site)
        if township_name:
            township_counter[township_name] = township_counter.get(township_name, 0) + 1

    township_options = [
        {'value': item[0], 'label': item[0]}
        for item in sorted(township_counter.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        'category_choices': list(HeritageSite.CATEGORY_CHOICES),
        'level_choices': list(HeritageSite.LEVEL_CHOICES),
        'township_options': township_options,
    }


def get_heritage_detail_payload(site_id):
    heritage = HeritageSite.objects.filter(pk=site_id).first()
    if not heritage:
        return None

    inspection_rows = []
    for record in InspectionRecord.objects.filter(site=heritage).order_by('-inspect_time')[:10]:
        inspection_rows.append(
            {
                'id': record.id,
                'inspect_time': record.inspect_time.strftime('%Y-%m-%d %H:%M') if record.inspect_time else '',
                'is_normal': record.is_normal,
                'issue_details': record.issue_details or '',
                'latitude': record.latitude,
                'longitude': record.longitude,
            }
        )

    return {
        'id': heritage.id,
        'name': heritage.name,
        'sip_code': heritage.sip_code,
        'category': heritage.category,
        'category_label': heritage.get_category_display(),
        'level': heritage.level,
        'level_label': heritage.get_level_display(),
        'address': heritage.address,
        'longitude': float(heritage.longitude),
        'latitude': float(heritage.latitude),
        'description': heritage.description,
        'manager': heritage.manager,
        'body_boundary_data': _parse_zone(heritage.body_boundary),
        'protection_zone_data': _parse_zone(heritage.protection_zone),
        'control_zone_data': _parse_zone(heritage.control_zone),
        'inspection_records': inspection_rows,
    }
