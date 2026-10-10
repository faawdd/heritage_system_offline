"""四普系统文物数据全量导入：抓取（线程池并发，仅网络/文件IO）+ 写库（任务线程串行，避免 SQLite 并发写锁）。"""
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connections, transaction
from django.utils import timezone

from core.models import (
    HeritageConstituent,
    HeritageDrawing,
    HeritageMaterial,
    HeritagePhoto,
    HeritageSipuRelation,
    HeritageSite,
    ImmovableHeritage,
    SipuDictItem,
    SipuImportJob,
)
from core.services.heritage_inference import infer_all
from core.services.sipu_client import (
    LIST_PAGE_SIZE,
    SipuAuthError,
    SipuClient,
    dms_to_decimal,
)

logger = logging.getLogger(__name__)

ALL_MODULES = ('constitute', 'points', 'boundary', 'photos', 'drawings', 'materials', 'related')
FILE_MODES = ('none', 'cover', 'photos', 'all')
COVER_HINT = ('全景', '全貌', '概貌', '远景', '鸟瞰', '整体')
DICT_FIELDS = (
    'changeType', 'searchtype', 'useType', 'industryapp', 'purpose', 'protectrule', 'protectelement',
    'specType', 'yearforcount', 'ownership', 'stateevaluation', 'isSingleArea', 'isPublishArea', 'isPublishControl',
)

CATEGORY_MAP = {
    '0100': 'GWZ', '0200': 'GMZ', '0300': 'GJZ', '0400': 'SKT', '0500': 'JDJW', '0600': 'QT',
}
RANK_MAP = {'1': 'GB', '2': 'SB', '3': 'XB', '4': 'DS'}
PRESERVATION_MAP = {'1': '好', '2': '较好', '3': '一般', '4': '较差', '5': '差'}
POINT_TYPE_TO_COORD = {'1': 'boundary', '3': 'marker', '2': 'other', '9': 'other'}


def _s(value):
    return '' if value is None else str(value).strip()


def _decimal(value, places=None):
    text = _s(value)
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return round(number, places) if places is not None else number


def _parse_date(text):
    text = _s(text)
    for fmt in ('%Y.%m.%d', '%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _aware(dt):
    return timezone.make_aware(dt) if dt and timezone.is_naive(dt) else dt


def _ownership_from_label(label):
    for key, code in (('国', 'state'), ('集体', 'collective'), ('私', 'private'), ('个人', 'private')):
        if key in label:
            return code
    return 'other' if label else ''


def _list(value):
    if not value:
        return []
    return [str(v) for v in (value if isinstance(value, (list, tuple)) else [value]) if v not in (None, '')]


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ''
    return value or ''


def _short_type_name(name):
    return re.split(r'[（(]', _s(name))[0][:30]


def normalize_modules(modules):
    if not modules:
        return list(ALL_MODULES)
    return [m for m in ALL_MODULES if m in set(modules)]


# ──────────────────────────────────────────────────────────────────────────
# 抓取（线程池内执行，不访问数据库）
# ──────────────────────────────────────────────────────────────────────────
class SiteFetcher:
    def __init__(self, client: SipuClient, options: dict, have_files: set):
        self.client = client
        self.modules = set(options['modules'])
        self.file_mode = options['file_mode']
        self.have_files = have_files
        self._link_labels = {}
        self._lock = threading.Lock()

    def _safe(self, payload, label, func, default):
        try:
            return func()
        except SipuAuthError:
            raise
        except Exception as exc:  # 单个子模块失败不影响其余数据，记入告警
            payload['warnings'].append(f'{label}：{exc}')
            return default

    def _link_label(self, code, photo_id):
        if not code.startswith('tstype'):
            return ''
        with self._lock:
            if code in self._link_labels:
                return self._link_labels[code]
        label = self.client.fetch_photo_link_label(photo_id)
        with self._lock:
            self._link_labels[code] = label
        return label

    def _save_file(self, cul_rid, folder, src, kind, sipu_id):
        if (kind, sipu_id) in self.have_files or not src:
            return ''
        data = self.client.download_image(src)
        if not data:
            return ''
        name = default_storage.save(
            f'heritage_sipu/{folder}/{cul_rid}/{os.path.basename(src)}', ContentFile(data),
        )
        return name

    def fetch(self, row):
        cul_rid = row['id']
        client = self.client
        payload = {'row': row, 'warnings': [], 'files': {}}
        payload['cover'] = client.fetch_form(cul_rid, 'cover')
        payload['basic'] = client.fetch_form(cul_rid, 'basic')

        if 'constitute' in self.modules:
            payload['constituents'] = self._safe(payload, '文物构成', lambda: [
                dict(r, _type=t)
                for t in ('1', '2')
                for r in client.fetch_rows('tBBdataConstituteController.do', cul_rid, f'&constituteType={t}')
            ], [])
        if 'points' in self.modules:
            payload['points'] = self._safe(
                payload, '测点坐标', lambda: client.fetch_rows('tBBdataPointsController.do', cul_rid), [])
        if 'boundary' in self.modules:
            payload['rings'] = self._safe(
                payload, '矢量范围', lambda: client.fetch_mapdata_rings(cul_rid),
                {'body': [], 'protection': [], 'control': []})
        if 'photos' in self.modules:
            photos = self._safe(payload, '照片', lambda: client.fetch_rows('tBBdataPhotoController.do', cul_rid), [])
            for photo in photos:
                photo['_link_label'] = self._safe(
                    payload, '照片类型', lambda p=photo: self._link_label(_s(p.get('constituteId')), p['id']), '')
            cover = next(
                (p for p in photos if any(h in (p['_link_label'] + _s(p.get('remark')) + _s(p.get('photoName'))) for h in COVER_HINT)),
                photos[0] if photos else None,
            )
            if cover is not None:
                cover['_is_cover'] = True
            if self.file_mode != 'none':
                for photo in photos:
                    if self.file_mode == 'cover' and not photo.get('_is_cover'):
                        continue
                    path = self._safe(payload, f'照片文件 {photo.get("id")}', lambda p=photo: self._save_file(
                        cul_rid, 'photos', _s(p.get('fileSrc')), 'photo', p['id']), '')
                    if path:
                        payload['files'][('photo', photo['id'])] = path
            payload['photos'] = photos
        if 'drawings' in self.modules:
            drawings = self._safe(payload, '图纸', lambda: client.fetch_rows('tBBdataDraftController.do', cul_rid), [])
            if self.file_mode == 'all':
                for item in drawings:
                    path = self._safe(payload, f'图纸文件 {item.get("id")}', lambda i=item: self._save_file(
                        cul_rid, 'drawings', _s(i.get('fileSrc')), 'drawing', i['id']), '')
                    if path:
                        payload['files'][('drawing', item['id'])] = path
            payload['drawings'] = drawings
        if 'materials' in self.modules:
            materials = self._safe(payload, '其他资料', lambda: client.fetch_rows(
                'tBBdataOtherController.do', cul_rid, '&fieldNameen=&svalue='), [])
            if self.file_mode == 'all':
                for item in materials:
                    path = self._safe(payload, f'资料文件 {item.get("id")}', lambda i=item: self._save_file(
                        cul_rid, 'materials', _s(i.get('fileSrc')), 'material', i['id']), '')
                    if path:
                        payload['files'][('material', item['id'])] = path
            payload['materials'] = materials
        if 'related' in self.modules:
            payload['special'] = self._safe(
                payload, '关联专项', lambda: client.fetch_rows('tBBdataSpecialController.do', cul_rid, '&svalue='), [])
            payload['threesurvey'] = self._safe(
                payload, '三普对应记录', lambda: client.fetch_rows('tBThreesurveyBasicController.do', cul_rid), [])
        return payload


# ──────────────────────────────────────────────────────────────────────────
# 写库（任务线程串行）
# ──────────────────────────────────────────────────────────────────────────
def _pick_center(points):
    for ptype in ('2', '1', '3', '9'):
        for p in points:
            if _s(p.get('measurePointType')) == ptype and p.get('lng') is not None and p.get('lat') is not None:
                return p
    return None


def _build_heritage_fields(payload, dicts):
    row, cover, basic = payload['row'], payload['cover'], payload['basic']
    bv, cv = basic['values'], cover['values']
    points = payload.get('points') or []
    center = _pick_center(points)
    region = cover['unnamed']

    lon = lat = alt = None
    if center:
        lon, lat = center['lng'], center['lat']
        alt = _decimal(center.get('altitude'), 2)
    else:
        lon, lat = dms_to_decimal(row.get('longitude')), dms_to_decimal(row.get('latitude'))

    subcategory = _s(bv.get('subcategory') or row.get('subcategory'))
    category_code = _s(_first(bv.get('category')) or row.get('category'))
    rank = _s(_first(bv.get('rank')) or row.get('rank'))
    state = _s(_first(bv.get('stateevaluation')))
    ownership = _first(bv.get('ownership'))
    protectelement_labels = basic['labels'].get('protectelement', {})
    threats = '、'.join(protectelement_labels.get(v, v) for v in (bv.get('protectelement') or []))

    fields = {
        'name': _s(bv.get('name') or row.get('name'))[:200],
        'era': _s(bv.get('year') or row.get('niandai'))[:100],
        'category': CATEGORY_MAP.get(category_code, 'QT'),
        'heritage_type': _short_type_name(dicts.get('category', {}).get(subcategory, '')),
        'province': _s(region[0] if len(region) > 0 else '')[:50],
        'city': _s(region[1] if len(region) > 1 else '')[:50],
        'county': _s(region[2] if len(region) > 2 else '')[:50],
        'address': _s(bv.get('address') or row.get('address'))[:500],
        'coordinate_system': 'CGCS2000',
        'area': _decimal(bv.get('area') or row.get('area'), 2),
        'preservation_status': PRESERVATION_MAP.get(state, ''),
        'threat_factors': threats,
        'county_code': _s(row.get('country'))[:12],
        'registration_type': _s(row.get('searchtype'))[:10],
        'change_type': _s(bv.get('changeType'))[:20],
        'era_stat': _list(bv.get('yearforcount')),
        'parent_unit_name': _s(bv.get('unitName'))[:200],
        'is_single_area': {'1': True, '0': False}.get(_s(bv.get('isSingleArea'))),
        'open_status': _s(_first(bv.get('useType')))[:10],
        'use_purposes': _list(bv.get('purpose')),
        'industries': _list(bv.get('industryapp')),
        'protect_measures': _list(bv.get('protectrule')),
        'listed_catalogs': _list(bv.get('specType')),
        'sipu_auditor': _s(cv.get('auditor'))[:50],
        'ownership': _ownership_from_label(basic['labels'].get('ownership', {}).get(_s(ownership), '')) if ownership else '',
        'ownership_detail': _s(bv.get('propertyManage'))[:200],
        'user_unit': _s(bv.get('owner'))[:200],
        'management_unit': _s(bv.get('vestin'))[:200],
        'protection_level': RANK_MAP.get(rank, ''),
        'has_protection_zone_announced': _s(bv.get('isPublishArea')) == '1',
        'has_construction_control_zone_announced': _s(bv.get('isPublishControl')) == '1',
        'description': _s(bv.get('brief')),
        'remarks': _s(bv.get('remark')),
        'collected_at': _aware(_parse_date(cv.get('collectdate'))),
        'reviewed_at': _aware(_parse_date(cv.get('auditdate'))),
        'coord_list': [
            {
                'type': POINT_TYPE_TO_COORD.get(_s(p.get('measurePointType')), 'other'),
                'longitude': p.get('lng'), 'latitude': p.get('lat'),
                'altitude': _s(p.get('altitude')), 'sourceTag': 'sipu',
                'description': _s(p.get('pointDesc')), 'remark': _s(p.get('remark')),
            }
            for p in points if p.get('lng') is not None and p.get('lat') is not None
        ],
    }
    if lon is not None and lat is not None:
        fields['longitude'] = round(Decimal(str(lon)), 8)
        fields['latitude'] = round(Decimal(str(lat)), 8)
    if alt is not None:
        fields['altitude'] = alt
    return fields


def _sync_children(model, heritage, items, build, keep_files=False):
    """按 sipu_id 增量同步子表：存在则更新（保留已下载文件），缺失则新增，四普端已删除的记录同步删除。"""
    existing = {obj.sipu_id: obj for obj in model.objects.filter(heritage=heritage)}
    seen = set()
    created = 0
    for order, item in enumerate(items, 1):
        sipu_id = _s(item.get('id'))
        values = build(item)
        values['sort_order'] = order
        obj = existing.get(sipu_id) if sipu_id else None
        if obj:
            for key, val in values.items():
                setattr(obj, key, val)
            obj.save()
        else:
            obj = model.objects.create(heritage=heritage, sipu_id=sipu_id, **values)
            created += 1
        if sipu_id:
            seen.add(sipu_id)
    stale = [obj.pk for sid, obj in existing.items() if sid not in seen or not sid]
    if stale:
        model.objects.filter(pk__in=stale).delete()
    return created


def _set_file(obj_field, payload, kind, sipu_id):
    path = payload['files'].get((kind, sipu_id))
    return path or None


def apply_payload(payload, dicts, options, site_index):
    """把一个文物点的抓取结果写入数据库，返回统计 dict。"""
    row = payload['row']
    cul_rid = row['id']
    code = _s(payload['cover']['values'].get('code') or row.get('code'))
    fields = _build_heritage_fields(payload, dicts)
    stats = {}

    with transaction.atomic():
        heritage = ImmovableHeritage.objects.filter(sipu_id=cul_rid).first()
        if heritage is None and code:
            heritage = ImmovableHeritage.objects.filter(survey_code=code, sipu_id__isnull=True).first()
        created = heritage is None
        if created:
            heritage = ImmovableHeritage()
            survey_code = code or f'SIPU-{cul_rid[:8]}'
            if ImmovableHeritage.objects.filter(survey_code=survey_code).exists():
                survey_code = f'{survey_code}#{cul_rid[:6]}'
            heritage.survey_code = survey_code
        elif code and heritage.survey_code != code and not ImmovableHeritage.objects.filter(survey_code=code).exists():
            heritage.survey_code = code

        for key, val in fields.items():
            setattr(heritage, key, val)
        heritage.sipu_id = cul_rid
        if heritage.longitude is None or heritage.latitude is None:
            heritage.longitude, heritage.latitude = Decimal('0'), Decimal('0')  # 四普未登记坐标
        heritage.sipu_synced_at = timezone.now()
        inferred = infer_all(
            address=fields.get('address'), region_names=payload['cover']['unnamed'],
            text='\n'.join(filter(None, [fields.get('description'), fields.get('remarks')])),
            name=fields.get('name'), threesurvey=payload.get('threesurvey') or [],
            photo_labels=[p.get('_link_label', '') for p in payload.get('photos') or []],
            change_label=payload['basic']['labels'].get('changeType', {}).get(fields.get('change_type', ''), ''),
        )
        filled = []
        for key, val in inferred.items():
            if val in (None, '', [], False) or getattr(heritage, key, None) not in (None, '', False, []):
                continue
            if key == 'protection_announced_date':
                val = _parse_date(val) if isinstance(val, str) else val
                if val is None:
                    continue
            setattr(heritage, key, val)
            filled.append(key)
        heritage.sipu_data = {'inferred': filled}
        if 'boundary' in options['modules']:
            rings = payload.get('rings') or {}
            heritage.body_boundary = rings.get('body') or []
            heritage.protection_zone = rings.get('protection') or []
            heritage.control_zone = rings.get('control') or []
        heritage.save()
        stats['created' if created else 'updated'] = 1

        if 'constitute' in options['modules']:
            _sync_children(HeritageConstituent, heritage, payload.get('constituents') or [], lambda i: {
                'constitute_type': _s(i.get('_type') or i.get('constituteType')) or '1',
                'name': _s(i.get('constituteName'))[:300], 'category': _s(i.get('category'))[:20],
                'number': _s(i.get('constituteNum'))[:50], 'area': _s(i.get('constituteArea'))[:50],
                'remark': _s(i.get('remark')),
            })
            stats['constituents'] = len(payload.get('constituents') or [])

        if 'points' in options['modules']:
            stats['points'] = len(payload.get('points') or [])

        if 'photos' in options['modules']:
            constituent_names = {c['id']: _s(c.get('constituteName')) for c in payload.get('constituents') or []}

            def build_photo(i):
                values = {
                    'caption': _s(i.get('remark') or i.get('photoName'))[:300],
                    'photo_no': _s(i.get('photoNo'))[:50], 'cameraman': _s(i.get('cameraman'))[:100],
                    'link_type': (i.get('_link_label') or constituent_names.get(_s(i.get('constituteId'))) or '')[:100],
                    'shot_at': _aware(_parse_date(i.get('photoTime'))),
                    'photo_type': 'overview',
                }
                lon, lat = dms_to_decimal(i.get('longitude')), dms_to_decimal(i.get('latitude'))
                if lon is not None and lat is not None and -180 <= lon <= 180 and -90 <= lat <= 90:
                    values['shot_longitude'] = round(Decimal(str(lon)), 8)
                    values['shot_latitude'] = round(Decimal(str(lat)), 8)
                path = payload['files'].get(('photo', i['id']))
                if path:
                    values['image'] = path
                return values

            all_photos = payload.get('photos') or []
            existing = {p.sipu_id: p for p in HeritagePhoto.objects.filter(heritage=heritage)}
            photos = [
                p for p in all_photos
                if payload['files'].get(('photo', p['id'])) or (existing.get(_s(p['id'])) and existing[_s(p['id'])].image)
            ]
            seen = set()
            for order, item in enumerate(photos):
                sid = _s(item.get('id'))
                values = build_photo(item)
                obj = existing.get(sid)
                if obj:
                    for key, val in values.items():
                        setattr(obj, key, val)
                    obj.save()
                else:
                    obj = HeritagePhoto.objects.create(
                        heritage=heritage, sipu_id=sid, is_cover=bool(item.get('_is_cover')), **values)
                seen.add(sid)
            remote_ids = {_s(p['id']) for p in all_photos}
            HeritagePhoto.objects.filter(heritage=heritage).exclude(sipu_id='').exclude(
                sipu_id__isnull=True).exclude(sipu_id__in=remote_ids).delete()
            stats['photos'] = len(all_photos)
            stats['photo_files'] = len(photos)

        if 'drawings' in options['modules']:
            def build_drawing(i):
                values = {
                    'name': _s(i.get('draftName'))[:300], 'counter': _s(i.get('counter'))[:100],
                    'scale': _s(i.get('scale'))[:50],
                    'drawer': _s(i.get('drawer'))[:100], 'draw_time': _s(i.get('drawTime'))[:50],
                    'link_type': _s(i.get('linkType'))[:20], 'remark': _s(i.get('remark')),
                }
                path = payload['files'].get(('drawing', i['id']))
                if path:
                    values['file'] = path
                return values
            _sync_children(HeritageDrawing, heritage, payload.get('drawings') or [], build_drawing)
            stats['drawings'] = len(payload.get('drawings') or [])

        if 'materials' in options['modules']:
            def build_material(i):
                values = {
                    'name': _s(i.get('otherName'))[:500], 'file_category': _s(i.get('fileCategory'))[:50],
                    'category': _s(i.get('category'))[:20], 'counter': _s(i.get('counter'))[:100],
                    'number': _s(i.get('number'))[:50], 'save_place': _s(i.get('saveplace'))[:300],
                    'remark': _s(i.get('remark')),
                }
                path = payload['files'].get(('material', i['id']))
                if path:
                    values['file'] = path
                return values
            _sync_children(HeritageMaterial, heritage, payload.get('materials') or [], build_material)
            stats['materials'] = len(payload.get('materials') or [])

        if 'related' in options['modules']:
            relation_rows = []
            for kind, key, cat_key in (
                (HeritageSipuRelation.KIND_SPECIAL, 'special', 'culTypename'),
                (HeritageSipuRelation.KIND_THREE_SURVEY, 'threesurvey', 'unitClass'),
            ):
                for item in payload.get(key) or []:
                    compact = {k: _s(v) for k, v in (
                        ('no', item.get('unit_no')), ('address', item.get('address')), ('year', item.get('year')),
                        ('category', item.get(cat_key)), ('rank', item.get('rank'))) if _s(v)}
                    relation_rows.append((kind, item, _s(item.get('unit_name'))[:300], compact))
            HeritageSipuRelation.objects.filter(heritage=heritage).delete()
            HeritageSipuRelation.objects.bulk_create([
                HeritageSipuRelation(
                    heritage=heritage, kind=kind, name=name, data=compact, sipu_id=_s(item.get('id')), sort_order=order)
                for order, (kind, item, name, compact) in enumerate(relation_rows, 1)
            ])
            stats['relations'] = len(relation_rows)

        if options.get('sync_sites') and 'boundary' in options['modules']:
            site = site_index.get(fields['name'])
            rings = payload.get('rings') or {}
            if site and (rings.get('body') or rings.get('protection') or rings.get('control')):
                import json as _json
                changed = []
                for attr, key in (('body_boundary', 'body'), ('protection_zone', 'protection'), ('control_zone', 'control')):
                    if rings.get(key) and (options['scope'] == 'all' or not getattr(site, attr)):
                        setattr(site, attr, _json.dumps(rings[key], ensure_ascii=False))
                        changed.append(attr)
                if changed:
                    site.save(update_fields=changed)
                    stats['sites_synced'] = 1
    return stats


# ──────────────────────────────────────────────────────────────────────────
# 任务调度
# ──────────────────────────────────────────────────────────────────────────
def _collect_rows(client, job, options):
    """分页拉取四普文物列表（每页 90 条）；scope=missing 时跳过本地已导入的记录。"""
    rows, page, total = [], 1, None
    # 区县审定端账号：由服务端按 userCounty 过滤，避免拉取全省/全国列表
    region = options.get('region_code') or ''
    options['user_county'] = region if len(region) == 6 else ''
    imported = set()
    if options['scope'] != 'all':
        imported = set(ImmovableHeritage.objects.exclude(sipu_id__isnull=True).values_list('sipu_id', flat=True))
    while True:
        page_rows, count = client.list_page(
            page, category=options.get('category', ''), keyword=options.get('keyword', ''),
            user_county=options.get('user_county', ''))
        if total is None:
            total = count
            if total and not page_rows:
                raise SipuAuthError('四普系统列表为空，请检查 Cookie')
        region = options.get('region_code') or ''
        rows.extend(
            r for r in page_rows
            if r.get('id') not in imported
            and (not region or _s(r.get('country') or r.get('city') or r.get('province')).startswith(region))
        )
        if not page_rows or page * LIST_PAGE_SIZE >= total:
            break
        if options['limit'] and len(rows) >= options['limit']:
            break
        page += 1
    if options['limit']:
        rows = rows[:options['limit']]
    return rows, total or 0


def _collect_dict_labels(payload, acc):
    for source in (payload['cover']['labels'], payload['basic']['labels']):
        for field, mapping in source.items():
            if field in DICT_FIELDS or field in ('rank', 'category', 'subcategory'):
                for code, label in (mapping or {}).items():
                    acc[(field, str(code))] = _s(label)[:100]


def _flush_dict_labels(acc):
    if not acc:
        return
    existing = {(d.field, d.code): d for d in SipuDictItem.objects.all()}
    create, update = [], []
    for (field, code), label in acc.items():
        item = existing.get((field, code))
        if item is None:
            create.append(SipuDictItem(field=field, code=code, label=label))
        elif item.label != label:
            item.label = label
            update.append(item)
    SipuDictItem.objects.bulk_create(create, ignore_conflicts=True)
    if update:
        SipuDictItem.objects.bulk_update(update, ['label'])
    acc.clear()


def run_import_job(job_id, cookie, options):
    job = SipuImportJob.objects.get(id=job_id)
    stats = {}
    failed_items = []
    dict_acc = {}
    try:
        client = SipuClient(cookie)
        dicts = client.load_dictionaries()
        account = client.detect_account_scope()
        stats['account_scope'] = account
        if not options.get('region_code') and account.get('role') == '15' and account.get('county'):
            options['region_code'] = account['county']
        rows, remote_total = _collect_rows(client, job, options)
        stats['remote_total'] = remote_total
        job.total = len(rows)
        job.stats = stats
        job.save(update_fields=['total', 'stats', 'updated_at'])

        site_index = {}
        if options.get('sync_sites'):
            site_index = {s.name: s for s in HeritageSite.objects.all()}

        processed = 0
        page_size = options['page_size']
        for start in range(0, len(rows), page_size):
            batch = rows[start:start + page_size]
            have_files = set()
            if options['file_mode'] != 'none':
                ids = [r['id'] for r in batch]
                have_files |= {
                    ('photo', p.sipu_id) for p in HeritagePhoto.objects.filter(
                        heritage__sipu_id__in=ids).exclude(image='')}
                have_files |= {
                    ('drawing', d.sipu_id) for d in HeritageDrawing.objects.filter(
                        heritage__sipu_id__in=ids).exclude(file='')}
                have_files |= {
                    ('material', m.sipu_id) for m in HeritageMaterial.objects.filter(
                        heritage__sipu_id__in=ids).exclude(file='')}
            fetcher = SiteFetcher(client, options, have_files)

            with ThreadPoolExecutor(max_workers=options['max_workers']) as executor:
                futures = {executor.submit(fetcher.fetch, row): row for row in batch}
                for future in as_completed(futures):
                    row = futures[future]
                    processed += 1
                    try:
                        payload = future.result()
                        _collect_dict_labels(payload, dict_acc)
                        site_stats = apply_payload(payload, dicts, options, site_index)
                        for key, val in site_stats.items():
                            stats[key] = stats.get(key, 0) + val
                        if payload['warnings']:
                            stats['warning_sites'] = stats.get('warning_sites', 0) + 1
                    except SipuAuthError:
                        raise
                    except Exception as exc:
                        logger.exception('四普文物导入失败: %s', row.get('name'))
                        failed_items.append({'id': row.get('id'), 'code': row.get('code'), 'name': row.get('name'), 'error': str(exc)[:300]})
                    job.processed = processed
                    job.matched = stats.get('created', 0) + stats.get('updated', 0)
                    job.failed_count = len(failed_items)
                    job.failed_items = failed_items[-200:]
                    job.stats = stats
                    job.save(update_fields=['processed', 'matched', 'failed_count', 'failed_items', 'stats', 'updated_at'])
            _flush_dict_labels(dict_acc)

        job.status = SipuImportJob.STATUS_SUCCESS
        job.save(update_fields=['status', 'updated_at'])
    except Exception as exc:
        logger.exception('四普数据导入任务失败: job_id=%s', job_id)
        job.status = SipuImportJob.STATUS_FAILED
        job.error_message = str(exc)[:1000]
        job.save(update_fields=['status', 'error_message', 'updated_at'])
    finally:
        try:
            _flush_dict_labels(dict_acc)
        finally:
            connections.close_all()


def start_import_job(user, cookie, options):
    job = SipuImportJob.objects.create(
        created_by=user if getattr(user, 'is_authenticated', False) else None, options=options)
    threading.Thread(target=run_import_job, args=(job.id, cookie, options), daemon=True).start()
    return job.id


def get_job_status(job_id):
    job = SipuImportJob.objects.filter(id=job_id).first()
    if not job:
        return None
    return {
        'job_id': str(job.id),
        'status': job.status,
        'total': job.total,
        'processed': job.processed,
        'matched': job.matched,
        'failed_count': job.failed_count,
        'failed': job.failed_items,
        'stats': job.stats,
        'error_message': job.error_message,
    }
