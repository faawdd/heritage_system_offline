from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError


TILE_PATH_RE = re.compile(r'^(?P<z>\d{1,2})/(?P<x>\d{1,9})/(?P<y>\d{1,9})\.(?P<ext>png|jpe?g|webp)$', re.IGNORECASE)
MAX_ARCHIVE_ENTRIES = 5_000_000
MAX_ARCHIVE_UNPACKED_BYTES = 20 * 1024 * 1024 * 1024
MAX_TILE_BYTES = 8 * 1024 * 1024
ALLOWED_FORMATS = {'png', 'jpg', 'jpeg', 'webp'}


def get_tile_root() -> Path:
    configured = os.environ.get('HERITAGE_TILE_DIR')
    if configured:
        return Path(configured).expanduser().resolve()
    data_dir = Path(os.environ.get('HERITAGE_DATA_DIR', settings.BASE_DIR)).expanduser().resolve()
    return data_dir / 'map-tiles'


def _manifest_path() -> Path:
    return get_tile_root() / 'catalog.json'


def list_tile_sets() -> list[dict]:
    path = _manifest_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_manifest(rows: list[dict]) -> None:
    root = get_tile_root()
    root.mkdir(parents=True, exist_ok=True)
    target = _manifest_path()
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(target)


def _safe_name(raw_name: str) -> str:
    name = Path(raw_name or '').name.strip()
    name = re.sub(r'[^\w\- .()\u4e00-\u9fff]', '_', name).strip(' .')
    return name[:80] or '离线地图'


def _metadata_number(metadata: dict[str, str], key: str) -> float | None:
    try:
        return float(metadata[key])
    except (KeyError, TypeError, ValueError):
        return None


def _inspect_mbtiles(path: Path) -> dict:
    try:
        connection = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'metadata', 'tiles'}.issubset(tables):
                raise ValidationError('MBTiles 文件必须包含 metadata 和 tiles 表')
            metadata = dict(connection.execute('SELECT name, value FROM metadata'))
            row = connection.execute('SELECT COUNT(*), MIN(zoom_level), MAX(zoom_level) FROM tiles').fetchone()
            if not row or not row[0]:
                raise ValidationError('MBTiles 文件中没有瓦片数据')
            image_format = str(metadata.get('format', '')).lower()
            if image_format not in ALLOWED_FORMATS:
                raise ValidationError('MBTiles 仅支持 PNG、JPEG 或 WebP 瓦片')
            bounds = None
            if metadata.get('bounds'):
                try:
                    bounds = [float(item) for item in metadata['bounds'].split(',')]
                    if len(bounds) != 4:
                        bounds = None
                except ValueError:
                    bounds = None
            return {
                'bounds': bounds,
                'format': 'jpg' if image_format == 'jpeg' else image_format,
                'max_zoom': int(row[2]),
                'min_zoom': int(row[1]),
                'scheme': str(metadata.get('scheme') or 'tms').lower(),
                'tile_count': int(row[0]),
                'title': str(metadata.get('name') or metadata.get('title') or path.stem)[:120],
            }
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ValidationError('无法读取 MBTiles 数据库') from exc


def _zip_entry_tile_path(info: zipfile.ZipInfo) -> tuple[int, int, int, str] | None:
    if info.is_dir():
        return None
    parts = PurePosixPath(info.filename.replace('\\', '/')).parts
    if any(part in {'..', ''} for part in parts):
        raise ValidationError('ZIP 中包含不安全的路径')
    relative = '/'.join(parts[-3:])
    match = TILE_PATH_RE.fullmatch(relative)
    if not match:
        return None
    zoom, column, row = (int(match.group(key)) for key in ('z', 'x', 'y'))
    if zoom > 30 or column >= 2**zoom or row >= 2**zoom:
        raise ValidationError(f'瓦片坐标超出范围：{relative}')
    extension = match.group('ext').lower()
    image_format = 'jpg' if extension in {'jpg', 'jpeg'} else extension
    return zoom, column, row, image_format


def _import_xyz_zip(source: Path, destination: Path, scheme: str) -> dict:
    tile_count = 0
    total_size = 0
    formats: set[str] = set()
    min_zoom = 30
    max_zoom = 0

    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ValidationError('ZIP 文件包含的条目过多')
            total_size = sum(item.file_size for item in entries)
            if total_size > MAX_ARCHIVE_UNPACKED_BYTES:
                raise ValidationError('解压后的瓦片数据超过 20 GiB 限制')
            for info in entries:
                tile_path = _zip_entry_tile_path(info)
                if tile_path is None:
                    continue
                if info.file_size > MAX_TILE_BYTES:
                    raise ValidationError(f'单张瓦片超过 8 MiB 限制：{info.filename}')
                zoom, column, row, image_format = tile_path
                target = destination / str(zoom) / str(column) / f'{row}.{image_format}'
                if target.exists():
                    raise ValidationError(f'ZIP 中存在重复瓦片坐标：{info.filename}')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as input_file, target.open('wb') as output_file:
                    shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
                tile_count += 1
                min_zoom = min(min_zoom, zoom)
                max_zoom = max(max_zoom, zoom)
                formats.add(image_format)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValidationError('无法读取 XYZ/TMS 瓦片 ZIP 文件') from exc

    if tile_count == 0:
        raise ValidationError('ZIP 中未找到 z/x/y.png、jpg 或 webp 瓦片')
    if len(formats) > 1:
        raise ValidationError('同一瓦片集不能混合多种图片格式')
    return {
        'bounds': None,
        'format': formats.pop(),
        'max_zoom': max_zoom,
        'min_zoom': min_zoom,
        'scheme': scheme,
        'tile_count': tile_count,
    }


def import_tile_set(uploaded_file, display_name: str = '', scheme: str = 'xyz') -> dict:
    root = get_tile_root()
    root.mkdir(parents=True, exist_ok=True)
    tile_id = uuid.uuid4().hex
    staging_dir = Path(tempfile.mkdtemp(prefix=f'.{tile_id}-', dir=root))
    source_path = staging_dir / Path(uploaded_file.name or 'tiles').name
    try:
        with source_path.open('wb') as output_file:
            for chunk in uploaded_file.chunks():
                output_file.write(chunk)
        extension = source_path.suffix.lower()
        if extension == '.mbtiles':
            metadata = _inspect_mbtiles(source_path)
            target_dir = root / tile_id
            target_dir.mkdir()
            target_path = target_dir / 'map.mbtiles'
            source_path.replace(target_path)
            kind = 'mbtiles'
        elif extension == '.zip':
            normalized_scheme = str(scheme or 'xyz').lower()
            if normalized_scheme not in {'xyz', 'tms'}:
                raise ValidationError('瓦片目录格式必须为 XYZ 或 TMS')
            target_dir = root / tile_id
            target_dir.mkdir()
            metadata = _import_xyz_zip(source_path, target_dir, normalized_scheme)
            kind = 'xyz'
        else:
            raise ValidationError('请选择 QGIS 导出的 .mbtiles 或 XYZ/TMS .zip 文件')

        row = {
            **metadata,
            'id': tile_id,
            'kind': kind,
            'name': _safe_name(display_name or metadata.get('title') or source_path.stem),
        }
        rows = list_tile_sets()
        rows.append(row)
        _save_manifest(rows)
        return row
    except Exception:
        shutil.rmtree(root / tile_id, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def delete_tile_set(tile_id: str) -> bool:
    rows = list_tile_sets()
    selected = next((item for item in rows if item.get('id') == tile_id), None)
    if selected is None:
        return False
    shutil.rmtree(get_tile_root() / tile_id, ignore_errors=True)
    _save_manifest([item for item in rows if item.get('id') != tile_id])
    return True


def read_tile(tile_id: str, zoom: int, column: int, row: int) -> tuple[bytes, str] | None:
    if min(zoom, column, row) < 0 or zoom > 30 or column >= 2**zoom or row >= 2**zoom:
        return None
    tile_set = next((item for item in list_tile_sets() if item.get('id') == tile_id), None)
    if tile_set is None:
        return None
    if tile_set['kind'] == 'mbtiles':
        database_path = get_tile_root() / tile_id / 'map.mbtiles'
        tile_row = (2**zoom - 1 - row) if tile_set.get('scheme', 'tms') == 'tms' else row
        try:
            connection = sqlite3.connect(f'file:{database_path.as_posix()}?mode=ro', uri=True)
            try:
                result = connection.execute(
                    'SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?',
                    (zoom, column, tile_row),
                ).fetchone()
                return (bytes(result[0]), tile_set['format']) if result else None
            finally:
                connection.close()
        except (OSError, sqlite3.Error):
            return None

    extension = tile_set['format']
    tile_row = (2**zoom - 1 - row) if tile_set.get('scheme') == 'tms' else row
    tile_path = get_tile_root() / tile_id / str(zoom) / str(column) / f'{tile_row}.{extension}'
    try:
        return (tile_path.read_bytes(), extension) if tile_path.is_file() else None
    except OSError:
        return None