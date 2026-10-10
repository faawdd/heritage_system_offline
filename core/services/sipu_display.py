"""四普补充字段的统一定义：API 序列化、编辑校验、预览页展示共用。"""
from core.models import SipuDictItem

# 字段名 -> (显示名, 类型)；类型：code=单选代码，codes=多选代码，text=文本，bool=是/否/未填
SIPU_FIELDS = [
    ('registration_type', '登记类型', 'code'),
    ('change_type', '变更类型', 'code'),
    ('era_stat', '年代（统计分期）', 'codes'),
    ('parent_unit_name', '所属文物保护单位', 'text'),
    ('is_single_area', '是否单一范围', 'bool'),
    ('open_status', '开放状况', 'code'),
    ('use_purposes', '使用用途', 'codes'),
    ('industries', '所属行业、系统', 'codes'),
    ('protect_measures', '已完成保护措施', 'codes'),
    ('listed_catalogs', '所列名录、规划和数据库', 'codes'),
    ('sipu_auditor', '审定人', 'text'),
]
SIPU_FIELD_NAMES = [name for name, _label, _kind in SIPU_FIELDS]

# 本地字段 -> 四普字典字段名（SipuDictItem.field）
DICT_FIELD_OF = {
    'registration_type': 'searchtype',
    'change_type': 'changeType',
    'era_stat': 'yearforcount',
    'open_status': 'useType',
    'use_purposes': 'purpose',
    'industries': 'industryapp',
    'protect_measures': 'protectrule',
    'listed_catalogs': 'specType',
}

INFERRED_LABELS = {
    'township': '乡镇/街道', 'village': '村/社区', 'previous_survey_code': '三普编号',
    'former_name': '曾用名', 'damage_cause': '损毁原因', 'is_disappeared': '是否消失',
    'disappear_reason': '消失原因', 'is_relocated': '是否搬迁', 'relocation_note': '搬迁说明',
    'protection_announced_batch': '公布批次', 'protection_announced_date': '公布日期',
    'has_marker_stele': '设有保护标志碑',
}


def load_dict_map():
    """{四普字典字段: {代码: 含义}}"""
    result = {}
    for item in SipuDictItem.objects.all():
        result.setdefault(item.field, {})[item.code] = item.label
    return result


def dict_choices(dict_map):
    """前端下拉选项：{本地字段: [{value, label}]}"""
    return {
        local: [{'value': code, 'label': label} for code, label in sorted(dict_map.get(remote, {}).items())]
        for local, remote in DICT_FIELD_OF.items()
    }


def serialize_scalar(item):
    return {name: getattr(item, name) for name in SIPU_FIELD_NAMES} | {'county_code': item.county_code}


def display_value(item, name, kind, dict_map):
    value = getattr(item, name)
    labels = dict_map.get(DICT_FIELD_OF.get(name, ''), {})
    if kind == 'codes':
        return '、'.join(labels.get(c, c) for c in (value or []))
    if kind == 'code':
        return labels.get(value, value) if value else ''
    if kind == 'bool':
        return {True: '是', False: '否'}.get(value, '')
    return value or ''


def display_rows(item, dict_map):
    """预览页用：[(显示名, 文本)]，仅包含有值的项。"""
    rows = [('行政区划代码', item.county_code)] if item.county_code else []
    for name, label, kind in SIPU_FIELDS:
        text = display_value(item, name, kind, dict_map)
        if text:
            rows.append((label, text))
    return rows


def inferred_labels(item):
    names = (item.sipu_data or {}).get('inferred') or []
    return [INFERRED_LABELS.get(n, n) for n in names]


def clean_codes(value):
    if not isinstance(value, (list, tuple)):
        return None
    return [str(v).strip() for v in value if str(v).strip()]
