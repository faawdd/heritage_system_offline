from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

try:
    from pyproj import CRS, Transformer
except Exception:
    CRS = None
    Transformer = None

Coord = Tuple[float, float]


@dataclass
class PlacemarkRecord:
    project_name: str
    source_folder: str
    geometry_type: str
    vertex_count: int
    source_lon: Optional[float]
    source_lat: Optional[float]
    target_lon: Optional[float]
    target_lat: Optional[float]
    cgcs2000_x: Optional[float]
    cgcs2000_y: Optional[float]
    project_coordinates: str


def strip_ns(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def child_text(node: ET.Element, child_name: str) -> str:
    for child in list(node):
        if strip_ns(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


def parse_kml_coordinates(text: str) -> List[Coord]:
    points: List[Coord] = []
    if not text:
        return points

    for token in text.replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
            points.append((lon, lat))
        except ValueError:
            continue
    return points


def get_representative_point(coords: Sequence[Coord], geometry_type: str) -> Optional[Coord]:
    if not coords:
        return None
    if geometry_type == "Point":
        return coords[0]
    lon_sum = sum(p[0] for p in coords)
    lat_sum = sum(p[1] for p in coords)
    return lon_sum / len(coords), lat_sum / len(coords)


def serialize_coords(coords: Sequence[Coord], decimals: int = 10) -> str:
    return ";".join(f"{lon:.{decimals}f},{lat:.{decimals}f}" for lon, lat in coords)


class CoordinateTransformer:
    def __init__(self, input_crs: str, output_crs: str):
        self.input_crs = input_crs
        self.output_crs = output_crs
        self._transformer_cache: Dict[Tuple[str, str], Any] = {}
        self._proj_cache: Dict[float, Any] = {}
        self._epsg_map = {
            "wgs84": "EPSG:4326",
            "cgcs2000": "EPSG:4490",
        }

    def _get_transformer(self, src: str, dst: str) -> Any:
        key = (src, dst)
        if key in self._transformer_cache:
            return self._transformer_cache[key]
        transformer = Transformer.from_crs(CRS.from_user_input(src), CRS.from_user_input(dst), always_xy=True)
        self._transformer_cache[key] = transformer
        return transformer

    @staticmethod
    def _central_meridian_3deg(lon: float) -> float:
        return round(lon / 3.0) * 3.0

    def _project_to_cgcs2000(self, lon: float, lat: float) -> Tuple[float, float]:
        if Transformer is None or CRS is None:
            raise RuntimeError("输出为 cgcs2000_proj 需要安装 pyproj")

        cm = self._central_meridian_3deg(lon)
        if cm not in self._proj_cache:
            proj_crs = CRS.from_proj4(
                f"+proj=tmerc +lat_0=0 +lon_0={cm} +k=1 +x_0=500000 +y_0=0 +ellps=GRS80 +units=m +no_defs"
            )
            src_epsg = self._epsg_map.get(self.input_crs, "EPSG:4326")
            transformer = Transformer.from_crs(CRS.from_user_input(src_epsg), proj_crs, always_xy=True)
            self._proj_cache[cm] = transformer

        x, y = self._proj_cache[cm].transform(lon, lat)
        return x, y

    def transform_lonlat(self, lon: float, lat: float) -> Tuple[float, float]:
        if self.output_crs == "cgcs2000_proj":
            if self.input_crs == "wgs84":
                if Transformer is None or CRS is None:
                    return lon, lat
                transformer = self._get_transformer("EPSG:4326", "EPSG:4490")
                return transformer.transform(lon, lat)
            return lon, lat

        if self.input_crs == self.output_crs:
            return lon, lat

        if Transformer is None or CRS is None:
            return lon, lat

        src = self._epsg_map[self.input_crs]
        dst = self._epsg_map[self.output_crs]
        transformer = self._get_transformer(src, dst)
        return transformer.transform(lon, lat)

    def to_projected_xy(self, lon: float, lat: float) -> Tuple[Optional[float], Optional[float]]:
        if self.output_crs != "cgcs2000_proj":
            return None, None
        return self._project_to_cgcs2000(lon, lat)


def extract_placemark_geometry(placemark: ET.Element) -> Tuple[str, List[Coord]]:
    point_coords: List[Coord] = []
    line_coords: List[Coord] = []
    polygon_coords: List[Coord] = []
    fallback_coords: List[Coord] = []

    for node in placemark.iter():
        if strip_ns(node.tag) == "coordinates":
            fallback_coords.extend(parse_kml_coordinates((node.text or "").strip()))

    for node in placemark.iter():
        tag = strip_ns(node.tag)
        if tag == "Point":
            for c in node.iter():
                if strip_ns(c.tag) == "coordinates":
                    point_coords.extend(parse_kml_coordinates((c.text or "").strip()))
        elif tag == "LineString":
            for c in node.iter():
                if strip_ns(c.tag) == "coordinates":
                    line_coords.extend(parse_kml_coordinates((c.text or "").strip()))
        elif tag == "Polygon":
            for c in node.iter():
                if strip_ns(c.tag) == "coordinates":
                    polygon_coords.extend(parse_kml_coordinates((c.text or "").strip()))

    if point_coords:
        return "Point", point_coords
    if polygon_coords:
        return "Polygon", polygon_coords
    if line_coords:
        return "LineString", line_coords
    if fallback_coords:
        return "Unknown", fallback_coords
    return "Unknown", []


def walk_kml(node: ET.Element, folder_stack: List[str], out_records: List[PlacemarkRecord], transformer: CoordinateTransformer):
    tag = strip_ns(node.tag)

    if tag in {"Document", "Folder"}:
        folder_name = child_text(node, "name") if tag == "Folder" else ""
        pushed = False
        if folder_name:
            folder_stack.append(folder_name)
            pushed = True

        for child in list(node):
            walk_kml(child, folder_stack, out_records, transformer)

        if pushed:
            folder_stack.pop()
        return

    if tag == "Placemark":
        name = child_text(node, "name") or "未命名地块"
        geometry_type, coords = extract_placemark_geometry(node)
        rep = get_representative_point(coords, geometry_type)

        source_lon = rep[0] if rep else None
        source_lat = rep[1] if rep else None
        target_lon = None
        target_lat = None
        cgcs2000_x = None
        cgcs2000_y = None

        transformed_coords: List[Coord] = []
        for lon, lat in coords:
            tlon, tlat = transformer.transform_lonlat(lon, lat)
            transformed_coords.append((tlon, tlat))

        if rep:
            target_lon, target_lat = transformer.transform_lonlat(rep[0], rep[1])
            cgcs2000_x, cgcs2000_y = transformer.to_projected_xy(rep[0], rep[1])

        out_records.append(
            PlacemarkRecord(
                project_name=name,
                source_folder="/".join(folder_stack),
                geometry_type=geometry_type,
                vertex_count=len(coords),
                source_lon=source_lon,
                source_lat=source_lat,
                target_lon=target_lon,
                target_lat=target_lat,
                cgcs2000_x=cgcs2000_x,
                cgcs2000_y=cgcs2000_y,
                project_coordinates=serialize_coords(transformed_coords),
            )
        )
        return

    for child in list(node):
        walk_kml(child, folder_stack, out_records, transformer)


def parse_ovkml(content: bytes, input_crs: str, output_crs: str) -> List[PlacemarkRecord]:
    root = ET.fromstring(content)
    transformer = CoordinateTransformer(input_crs=input_crs, output_crs=output_crs)
    records: List[PlacemarkRecord] = []
    walk_kml(root, [], records, transformer)
    return records


def extract_kml_from_kmz(content: bytes) -> bytes:
    """
    从KMZ/OVKMZ（ZIP文件）中提取KML内容。
    规则：优先查找根目录的.kml文件，否则递归查找第一个.kml文件。
    """
    try:
        with zipfile.ZipFile(io.BytesIO(content), 'r') as zip_file:
            # 首先查找根目录KML文件
            for name in zip_file.namelist():
                if name.endswith('.kml') and '/' not in name:
                    return zip_file.read(name)
            
            # 如果根目录没有，递归查找第一个KML文件
            for name in zip_file.namelist():
                if name.endswith('.kml'):
                    return zip_file.read(name)
            
            raise ValueError('KMZ/OVKMZ文件中未找到.kml文件')
    except zipfile.BadZipFile:
        raise ValueError('不是有效的ZIP文件')


def parse_kml_or_kmz(content: bytes, input_crs: str, output_crs: str) -> Tuple[List[PlacemarkRecord], str]:
    """
    解析KML/OVKML/KMZ/OVKMZ文件。
    返回值: (records列表, 文件格式字符串)
    """
    # 尝试识别文件格式
    file_format = 'kml'
    
    # 尝试作为KML/OVKML直接解析
    try:
        root = ET.fromstring(content)
        transformer = CoordinateTransformer(input_crs=input_crs, output_crs=output_crs)
        records: List[PlacemarkRecord] = []
        walk_kml(root, [], records, transformer)
        return records, file_format
    except ET.ParseError:
        pass
    
    # 尝试作为KMZ/OVKMZ解析
    try:
        kml_content = extract_kml_from_kmz(content)
        file_format = 'kmz'
        root = ET.fromstring(kml_content)
        transformer = CoordinateTransformer(input_crs=input_crs, output_crs=output_crs)
        records: List[PlacemarkRecord] = []
        walk_kml(root, [], records, transformer)
        return records, file_format
    except Exception as e:
        raise ValueError(f'无法解析文件：{str(e)}')



def build_projectaudit_rows(records: Sequence[PlacemarkRecord]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for r in records:
        rows.append(
            {
                "project_name": r.project_name,
                "project_unit": "",
                "construction_content": "",
                "project_scale": "",
                "project_coordinates": r.project_coordinates,
                "project_lon": "" if r.target_lon is None else f"{r.target_lon:.10f}",
                "project_lat": "" if r.target_lat is None else f"{r.target_lat:.10f}",
                "workflow_status": "received",
                "remarks": f"来源文件夹:{r.source_folder or '-'}; 几何:{r.geometry_type}; 顶点:{r.vertex_count}",
            }
        )
    return rows


def rows_to_csv(fieldnames: Sequence[str], rows: Sequence[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def build_csv_outputs(records: Sequence[PlacemarkRecord]) -> Tuple[str, str]:
    project_rows = build_projectaudit_rows(records)
    project_fields = [
        "project_name",
        "project_unit",
        "construction_content",
        "project_scale",
        "project_coordinates",
        "project_lon",
        "project_lat",
        "workflow_status",
        "remarks",
    ]

    detail_rows: List[Dict[str, Any]] = []
    for r in records:
        detail_rows.append(
            {
                "project_name": r.project_name,
                "source_folder": r.source_folder,
                "geometry_type": r.geometry_type,
                "vertex_count": r.vertex_count,
                "source_lon": "" if r.source_lon is None else f"{r.source_lon:.10f}",
                "source_lat": "" if r.source_lat is None else f"{r.source_lat:.10f}",
                "target_lon": "" if r.target_lon is None else f"{r.target_lon:.10f}",
                "target_lat": "" if r.target_lat is None else f"{r.target_lat:.10f}",
                "cgcs2000_x": "" if r.cgcs2000_x is None else f"{r.cgcs2000_x:.3f}",
                "cgcs2000_y": "" if r.cgcs2000_y is None else f"{r.cgcs2000_y:.3f}",
                "project_coordinates": r.project_coordinates,
            }
        )

    detail_fields = [
        "project_name",
        "source_folder",
        "geometry_type",
        "vertex_count",
        "source_lon",
        "source_lat",
        "target_lon",
        "target_lat",
        "cgcs2000_x",
        "cgcs2000_y",
        "project_coordinates",
    ]

    return rows_to_csv(project_fields, project_rows), rows_to_csv(detail_fields, detail_rows)
