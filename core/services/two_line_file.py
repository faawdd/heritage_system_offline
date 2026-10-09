import io
import math
import zipfile
import xml.etree.ElementTree as ET


MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_KML_BYTES = 100 * 1024 * 1024
SUPPORTED_EXTENSIONS = {'.ovkml', '.ovkmz', '.kml', '.kmz'}


def _local_name(tag):
    return tag.rsplit('}', 1)[-1]


def _extract_kml(content, filename):
    extension = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError('仅支持 OVKML、OVKMZ、KML、KMZ 文件')
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError('文件为空或超过 50 MB')

    if extension in {'.ovkmz', '.kmz'}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                candidates = [
                    info for info in archive.infolist()
                    if not info.is_dir() and info.filename.lower().endswith(('.kml', '.ovkml'))
                ]
                if not candidates:
                    raise ValueError('KMZ 压缩包中未找到 KML 文件')
                info = next((item for item in candidates if '/' not in item.filename), candidates[0])
                if info.file_size > MAX_KML_BYTES:
                    raise ValueError('压缩包内 KML 文件超过 100 MB')
                return archive.read(info)
        except zipfile.BadZipFile as exc:
            raise ValueError('KMZ/OVKMZ 不是有效的 ZIP 文件') from exc
    return content


def _parse_coordinates(text):
    points = []
    for token in (text or '').replace('\n', ' ').replace('\t', ' ').split():
        parts = token.split(',')
        if len(parts) < 2:
            continue
        try:
            longitude, latitude = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if not math.isfinite(longitude) or not math.isfinite(latitude):
            continue
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError('坐标超出经纬度范围，请确认文件坐标系为 WGS84/CGCS2000 经纬度')
        points.append([longitude, latitude])
    return points


def _close_ring(points):
    if len(points) < 3:
        return None
    if points[0] != points[-1]:
        points.append(points[0][:])
    if len(points) < 4:
        return None
    return points


def _placemark_rings(placemark):
    rings = []
    for polygon in (item for item in placemark.iter() if _local_name(item.tag) == 'Polygon'):
        outer = next((item for item in polygon if _local_name(item.tag) == 'outerBoundaryIs'), None)
        if outer is None:
            continue
        coordinate_node = next((item for item in outer.iter() if _local_name(item.tag) == 'coordinates'), None)
        ring = _close_ring(_parse_coordinates(coordinate_node.text if coordinate_node is not None else ''))
        if ring:
            rings.append(ring)

    for line in (item for item in placemark.iter() if _local_name(item.tag) == 'LineString'):
        coordinate_node = next((item for item in line.iter() if _local_name(item.tag) == 'coordinates'), None)
        ring = _close_ring(_parse_coordinates(coordinate_node.text if coordinate_node is not None else ''))
        if ring:
            rings.append(ring)
    return rings


def parse_two_line_file(content, filename, zone_type='auto'):
    """Return protection/control rings from a KML-family upload."""
    if zone_type not in {'auto', 'protection', 'control'}:
        raise ValueError('两线类型参数非法')
    kml_content = _extract_kml(content, filename)
    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError as exc:
        raise ValueError('KML/XML 文件解析失败') from exc
    if _local_name(root.tag) != 'kml':
        raise ValueError('文件根节点不是 KML')

    result = {'protection': [], 'control': []}
    counts = {'protection': 0, 'control': 0}

    def visit(node, folder_names):
        tag = _local_name(node.tag)
        name_node = next((child for child in node if _local_name(child.tag) == 'name'), None)
        name = (name_node.text or '').strip() if name_node is not None else ''
        next_folders = folder_names + ([name] if tag == 'Folder' and name else [])

        if tag == 'Placemark':
            labels = ' '.join(next_folders + ([name] if name else []))
            normalized_labels = labels.lower()
            if any(marker in normalized_labels for marker in ('_dimension_', '_text_', '标注', '注记')):
                return
            if '保护范围' in labels:
                kind = 'protection'
            elif any(label in labels for label in ('建控', '建设控制', '控制地带')):
                kind = 'control'
            elif zone_type != 'auto':
                kind = zone_type
            else:
                kind = None

            if kind:
                rings = _placemark_rings(node)
                result[kind].extend(rings)
                counts[kind] += len(rings)
            return

        for child in node:
            if _local_name(child.tag) in {'Document', 'Folder', 'Placemark'}:
                visit(child, next_folders)

    visit(root, [])
    if not result['protection'] and not result['control']:
        if zone_type == 'auto':
            raise ValueError('未识别到保护范围或建控地带要素；请为未标注的 KML 选择两线类型')
        raise ValueError('所选两线类型下未找到有效的面或闭合边界线')
    return result, counts

def parse_body_boundary_file(content, filename):
    """Return body (本体) boundary rings from a KML-family upload.

    Features explicitly labelled as 保护范围 / 建控地带 (the "two lines") and
    annotation features are ignored; every other polygon / closed line counts.
    """
    kml_content = _extract_kml(content, filename)
    try:
        root = ET.fromstring(kml_content)
    except ET.ParseError as exc:
        raise ValueError('KML/XML 文件解析失败') from exc
    if _local_name(root.tag) != 'kml':
        raise ValueError('文件根节点不是 KML')

    rings = []

    def visit(node, folder_names):
        tag = _local_name(node.tag)
        name_node = next((child for child in node if _local_name(child.tag) == 'name'), None)
        name = (name_node.text or '').strip() if name_node is not None else ''
        next_folders = folder_names + ([name] if tag == 'Folder' and name else [])

        if tag == 'Placemark':
            labels = ' '.join(next_folders + ([name] if name else []))
            if any(marker in labels.lower() for marker in ('_dimension_', '_text_', '标注', '注记')):
                return
            if any(label in labels for label in ('保护范围', '建控', '建设控制', '控制地带')):
                return
            rings.extend(_placemark_rings(node))
            return

        for child in node:
            if _local_name(child.tag) in {'Document', 'Folder', 'Placemark'}:
                visit(child, next_folders)

    visit(root, [])
    if not rings:
        raise ValueError('未在文件中找到有效的本体范围面或闭合边界线')
    return rings


def normalize_boundary_rings(value):
    """Validate JSON text / list of rings [[ [lon, lat], ... ], ...]; return rings (closed)."""
    import json

    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise ValueError('坐标必须是合法的 JSON') from exc
    if not isinstance(value, list):
        raise ValueError('坐标格式错误，应为多边形环数组')
    rings = []
    for ring in value:
        if not isinstance(ring, list):
            raise ValueError('坐标格式错误，每个环应为点数组')
        points = []
        for point in ring:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise ValueError('坐标点格式错误，应为 [经度, 纬度]')
            try:
                lon, lat = float(point[0]), float(point[1])
            except (TypeError, ValueError) as exc:
                raise ValueError('坐标点必须是数字') from exc
            if not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError('坐标超出经纬度范围')
            points.append([lon, lat])
        closed = _close_ring(points)
        if closed is None:
            raise ValueError('每个环至少需要 3 个不同的坐标点')
        rings.append(closed)
    return rings
