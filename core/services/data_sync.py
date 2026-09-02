"""在线版与离线版系统之间的数据同步：导出/导入 ZIP 数据包。

数据包结构::

    manifest.json                  # 数据包元信息
    data/<app>.<model>.json        # Django 序列化后的业务数据
    media/<相对路径>               # 业务数据引用到的上传文件（可选）
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from collections import OrderedDict
from pathlib import Path, PurePosixPath

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import models as django_models
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PACKAGE_FORMAT = 'heritage-sync'
PACKAGE_VERSION = 1

MANIFEST_NAME = 'manifest.json'
DATA_DIR_NAME = 'data'
MEDIA_DIR_NAME = 'media'

# 解压防护：限制成员数量与解压后总体积，避免 zip bomb。
MAX_MEMBER_COUNT = 200000
MAX_UNCOMPRESSED_BYTES = 4 * 1024 * 1024 * 1024

# 数据集按导入依赖顺序声明：先账号与系统配置，再业务数据。
SYNC_DATASETS = OrderedDict([
    ('account', {
        'label': '用户与权限',
        'description': '登录账号、用户档案与角色绑定',
        'models': ['auth.User', 'core.UserProfile'],
    }),
    ('system', {
        'label': '系统配置',
        'description': '菜单、数据字典与系统参数',
        'models': ['system.Menu', 'system.DictionaryType', 'system.DictionaryItem', 'system.SystemConfig'],
    }),
    ('heritage', {
        'label': '文物档案',
        'description': '不可移动文物档案、采集记录与照片',
        'models': ['core.HeritageSite', 'core.ImmovableHeritage', 'core.HeritagePhoto'],
    }),
    ('inspection', {
        'label': '巡查记录',
        'description': '基层巡查登记与现场照片',
        'models': ['core.InspectionRecord'],
    }),
    ('project', {
        'label': '项目管理',
        'description': '建设项目审批、现场照片与流转日志',
        'models': [
            'core.ProjectAudit',
            'core.LandUseProjectApproval',
            'core.LandUseProjectFieldPhoto',
            'core.LandUseProjectOperationLog',
        ],
    }),
    ('gis', {
        'label': 'KML与坐标',
        'description': 'KML 叠加检查记录与坐标数据',
        'models': ['core.KmlUploadRecord', 'core.Coordinate'],
    }),
])

DEFAULT_DATASETS = ['heritage', 'inspection', 'project', 'gis']

IMPORT_MODE_MERGE = 'merge'
IMPORT_MODE_REPLACE = 'replace'


class DataSyncError(Exception):
    """数据包格式或内容不合法。"""


def _media_root() -> Path:
    return Path(str(settings.MEDIA_ROOT)).resolve()


def _get_model(model_label: str):
    app_label, model_name = model_label.split('.', 1)
    return apps.get_model(app_label, model_name)


def _data_member_name(model) -> str:
    return f'{DATA_DIR_NAME}/{model._meta.label_lower}.json'


def _file_field_names(model) -> list:
    return [
        field.name for field in model._meta.get_fields()
        if isinstance(field, django_models.FileField)
    ]


def normalize_datasets(raw_datasets) -> list:
    """过滤出受支持的数据集键，保持声明顺序。"""
    if not raw_datasets:
        return list(DEFAULT_DATASETS)
    if isinstance(raw_datasets, str):
        raw_datasets = [item.strip() for item in raw_datasets.split(',')]
    requested = {str(item).strip() for item in raw_datasets if str(item).strip()}
    selected = [key for key in SYNC_DATASETS if key in requested]
    if not selected:
        raise DataSyncError('未选择任何有效的同步数据集。')
    return selected


def get_dataset_overview() -> list:
    """返回各数据集的当前记录数，供页面展示。"""
    overview = []
    for key, meta in SYNC_DATASETS.items():
        models_info = []
        total = 0
        for model_label in meta['models']:
            try:
                model = _get_model(model_label)
            except LookupError:
                continue
            count = model.objects.count()
            total += count
            models_info.append({
                'model': model_label,
                'label': str(model._meta.verbose_name),
                'count': count,
            })
        overview.append({
            'key': key,
            'label': meta['label'],
            'description': meta['description'],
            'count': total,
            'models': models_info,
            'default_selected': key in DEFAULT_DATASETS,
        })
    return overview


def _collect_media_relpaths(model, queryset) -> set:
    field_names = _file_field_names(model)
    if not field_names:
        return set()

    relpaths = set()
    for obj in queryset.iterator():
        for field_name in field_names:
            file_field = getattr(obj, field_name, None)
            name = getattr(file_field, 'name', '') or ''
            if name:
                relpaths.add(name.replace('\\', '/').lstrip('/'))
    return relpaths


def build_export_package(datasets=None, include_media: bool = True) -> tuple:
    """构建同步数据包，返回 (文件名, 字节内容)。"""
    selected = normalize_datasets(datasets)

    buffer = io.BytesIO()
    model_entries = []
    media_relpaths = set()

    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for dataset_key in selected:
            for model_label in SYNC_DATASETS[dataset_key]['models']:
                try:
                    model = _get_model(model_label)
                except LookupError:
                    logger.warning('数据同步导出跳过未知模型: %s', model_label)
                    continue

                queryset = model.objects.all().order_by('pk')
                payload = serializers.serialize('json', queryset.iterator(), indent=1)
                member_name = _data_member_name(model)
                archive.writestr(member_name, payload)
                model_entries.append({
                    'dataset': dataset_key,
                    'model': model._meta.label,
                    'file': member_name,
                    'count': queryset.count(),
                })

                if include_media:
                    media_relpaths |= _collect_media_relpaths(model, queryset)

        media_total_bytes = 0
        media_count = 0
        if include_media and media_relpaths:
            media_root = _media_root()
            for relpath in sorted(media_relpaths):
                source = (media_root / relpath).resolve()
                if not str(source).startswith(str(media_root)) or not source.is_file():
                    continue
                archive.write(source, f'{MEDIA_DIR_NAME}/{relpath}')
                media_total_bytes += source.stat().st_size
                media_count += 1

        manifest = {
            'format': PACKAGE_FORMAT,
            'version': PACKAGE_VERSION,
            'generated_at': timezone.now().isoformat(),
            'system_version': _system_version(),
            'datasets': selected,
            'models': model_entries,
            'include_media': bool(include_media),
            'media': {'count': media_count, 'total_bytes': media_total_bytes},
        }
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))

    filename = f"heritage-sync-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}.zip"
    return filename, buffer.getvalue()


def _system_version() -> str:
    configured = getattr(settings, 'SYS_VERSION', '')
    if configured:
        return str(configured)
    try:
        from heritage_system.version import VERSION

        if isinstance(VERSION, dict):
            return str(VERSION.get('version') or '')
        return str(VERSION)
    except Exception:
        return ''


def read_package_manifest(file_obj) -> dict:
    """仅读取数据包元信息，用于导入前预览。"""
    with zipfile.ZipFile(file_obj) as archive:
        return _load_manifest(archive)


def _load_manifest(archive: zipfile.ZipFile) -> dict:
    try:
        raw = archive.read(MANIFEST_NAME)
    except KeyError:
        raise DataSyncError('数据包缺少 manifest.json，不是有效的同步数据包。')

    try:
        manifest = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DataSyncError('数据包的 manifest.json 无法解析。')

    if manifest.get('format') != PACKAGE_FORMAT:
        raise DataSyncError('数据包格式不匹配，请使用本系统导出的同步包。')
    if int(manifest.get('version') or 0) > PACKAGE_VERSION:
        raise DataSyncError('数据包版本高于当前系统支持的版本，请先升级系统。')
    return manifest


def _safe_media_relpath(member_name: str):
    """校验并返回 media 成员的安全相对路径，非法路径返回 None。"""
    pure = PurePosixPath(member_name)
    if pure.is_absolute() or len(pure.parts) < 2 or pure.parts[0] != MEDIA_DIR_NAME:
        return None
    relparts = pure.parts[1:]
    if any(part in {'..', ''} for part in relparts):
        return None
    return PurePosixPath(*relparts)


def _guard_archive(archive: zipfile.ZipFile) -> None:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise DataSyncError('数据包内文件数量超出安全上限。')
    total = sum(info.file_size for info in infos)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise DataSyncError('数据包解压后体积超出安全上限。')


def apply_import_package(file_obj, datasets=None, mode: str = IMPORT_MODE_MERGE,
                         import_media: bool = True) -> dict:
    """导入同步数据包，返回导入统计报告。"""
    if mode not in {IMPORT_MODE_MERGE, IMPORT_MODE_REPLACE}:
        mode = IMPORT_MODE_MERGE

    try:
        archive = zipfile.ZipFile(file_obj)
    except zipfile.BadZipFile:
        raise DataSyncError('文件不是有效的 ZIP 数据包。')

    with archive:
        _guard_archive(archive)
        manifest = _load_manifest(archive)

        package_datasets = [key for key in SYNC_DATASETS if key in set(manifest.get('datasets') or [])]
        if not package_datasets:
            raise DataSyncError('数据包中没有可识别的数据集。')

        if datasets:
            requested = set(normalize_datasets(datasets))
            selected = [key for key in package_datasets if key in requested]
            if not selected:
                raise DataSyncError('所选数据集在该数据包中不存在。')
        else:
            selected = package_datasets

        details = []
        total_imported = 0
        total_skipped = 0

        with transaction.atomic():
            for dataset_key in selected:
                for model_label in SYNC_DATASETS[dataset_key]['models']:
                    try:
                        model = _get_model(model_label)
                    except LookupError:
                        continue

                    member_name = _data_member_name(model)
                    try:
                        payload = archive.read(member_name)
                    except KeyError:
                        continue

                    if mode == IMPORT_MODE_REPLACE:
                        model.objects.all().delete()

                    imported, skipped, errors = _load_model_objects(payload, model_label)
                    total_imported += imported
                    total_skipped += skipped
                    details.append({
                        'dataset': dataset_key,
                        'model': model._meta.label,
                        'label': str(model._meta.verbose_name),
                        'imported': imported,
                        'skipped': skipped,
                        'errors': errors[:5],
                    })

        media_imported = _restore_media(archive) if import_media else 0

    return {
        'mode': mode,
        'datasets': selected,
        'imported_count': total_imported,
        'skipped_count': total_skipped,
        'media_count': media_imported,
        'details': details,
        'source': {
            'generated_at': manifest.get('generated_at', ''),
            'system_version': manifest.get('system_version', ''),
        },
    }


def _load_model_objects(payload: bytes, model_label: str) -> tuple:
    imported = 0
    skipped = 0
    errors = []

    try:
        deserialized = list(serializers.deserialize('json', payload.decode('utf-8'), ignorenonexistent=True))
    except Exception as exc:
        raise DataSyncError(f'{model_label} 数据解析失败：{exc}')

    for item in deserialized:
        try:
            with transaction.atomic():
                item.save()
        except Exception as exc:
            skipped += 1
            errors.append(f'pk={getattr(item.object, "pk", "?")}: {exc}')
        else:
            imported += 1

    return imported, skipped, errors


def _restore_media(archive: zipfile.ZipFile) -> int:
    media_root = _media_root()
    restored = 0

    for info in archive.infolist():
        if info.is_dir():
            continue
        relpath = _safe_media_relpath(info.filename)
        if relpath is None:
            continue

        target = (media_root / Path(*relpath.parts)).resolve()
        if os.path.commonpath([str(media_root), str(target)]) != str(media_root):
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, open(target, 'wb') as dest:
            dest.write(source.read())
        restored += 1

    return restored
