import json
import re

from core.models import HeritageSite, InspectionRecord


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


def _extract_township_name(address):
    if not address:
        return ''

    text = str(address).strip()
    for keyword, standard_name in TOWNSHIP_NORMALIZATION_RULES:
        if keyword in text:
            return standard_name

    match = re.search(r'鄯善县(?:吐鲁番市鄯善县)*(?:东北)?([\u4e00-\u9fa5]{1,12}?(?:回族乡|乡|镇|街道))', text)
    if match:
        return match.group(1)

    return ''


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
    for site in HeritageSite.objects.all().only('id', 'name', 'longitude', 'latitude', 'level', 'body_boundary'):
        try:
            lng = float(site.longitude)
            lat = float(site.latitude)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                'id': site.id,
                'name': site.name,
                'lng': lng,
                'lat': lat,
                'level': site.level,
                'level_label': site.get_level_display(),
                # 本体边界环列表（[[[lon,lat],...],...]），供前端放大后渲染实际边界范围。
                'body_boundary': _parse_zone(site.body_boundary),
            }
        )
    return rows


def get_heritage_stats_meta():
    township_counter = {}
    for address in HeritageSite.objects.values_list('address', flat=True):
        township_name = _extract_township_name(address)
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
        'protection_zone_data': _parse_zone(heritage.protection_zone),
        'control_zone_data': _parse_zone(heritage.control_zone),
        'inspection_records': inspection_rows,
    }
