#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
将奥维互动地图导出的 OVKML/KML 转为可导入 Django ProjectAudit 模型的 CSV。

功能：
1) 递归遍历 Document/Folder/Placemark，适配复杂嵌套。
2) 提取 Placemark 名称与坐标（Point / LineString / Polygon）。
3) 提供坐标系开关：WGS84 / CGCS2000 / CGCS2000投影(米)。
4) 输出两份 CSV：
   - *_projectaudit.csv: 字段对齐 core.ProjectAudit，可直接导入。
   - *_detail.csv: 额外保留几何类型、顶点数、投影坐标等信息。

依赖：
- 标准库（必需）
- pyproj（可选，做严格 CRS 转换时建议安装）

示例：
python ovkml_to_project_csv.py --input sample.ovkml --output-dir ./out \
  --input-crs wgs84 --output-crs cgcs2000

python ovkml_to_project_csv.py --input sample.ovkml --output-dir ./out \
  --input-crs wgs84 --output-crs cgcs2000_proj
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
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
        pieces = token.split(",")
        if len(pieces) < 2:
            continue
        try:
            lon = float(pieces[0])
            lat = float(pieces[1])
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
    """
    支持：
    - wgs84 <-> cgcs2000（经纬度）
    - geodetic -> cgcs2000_proj（高斯/横轴墨卡托投影，单位米）

    说明：WGS84 与 CGCS2000 在多数业务场景下差异很小。
    若未安装 pyproj，将对 geodetic<->geodetic 走近似直通；
    对投影模式则抛错提醒安装 pyproj。
    """

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
            raise RuntimeError("输出为 cgcs2000_proj 需要安装 pyproj：pip install pyproj")

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
            # 投影模式下，为保持 ProjectAudit.project_lon/project_lat 可用，仍返回经纬度（CGCS2000）
            # 并在 detail 里单独输出 X/Y。
            if self.input_crs == "wgs84":
                if Transformer is None or CRS is None:
                    return lon, lat
                transformer = self._get_transformer("EPSG:4326", "EPSG:4490")
                return transformer.transform(lon, lat)
            if self.input_crs == "cgcs2000":
                return lon, lat
            return lon, lat

        if self.input_crs == self.output_crs:
            return lon, lat

        if Transformer is None or CRS is None:
            # 无 pyproj 时，geodetic 之间按近似直通
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
        tag = strip_ns(node.tag)
        if tag != "coordinates":
            continue

        coords = parse_kml_coordinates((node.text or "").strip())
        if not coords:
            continue

        parent = strip_ns(node.getparent().tag) if hasattr(node, "getparent") else ""
        # xml.etree 没有 getparent；下面通过祖先标签再判断
        ancestors = []
        # 退化处理：用节点文本所在路径判断几何类型
        # 因 xml.etree 不提供 parent，采用 string 序列化前后文不稳，这里转为“先分类后优先”策略：
        # 若 Placemark 下有 Point/Polygon/LineString 对应的 coordinates，将分别收集。
        fallback_coords.extend(coords)

    # 二次扫描：按几何节点精确抓取
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

        project_coordinates = serialize_coords(transformed_coords)

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
                project_coordinates=project_coordinates,
            )
        )
        return

    for child in list(node):
        walk_kml(child, folder_stack, out_records, transformer)


def write_projectaudit_csv(path: Path, records: Sequence[PlacemarkRecord]):
    fields = [
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(
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


def write_detail_csv(path: Path, records: Sequence[PlacemarkRecord]):
    fields = [
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
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow(
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


def write_preview_json(path: Path, records: Sequence[PlacemarkRecord]):
    payload = []
    for r in records:
        payload.append(
            {
                "project_name": r.project_name,
                "project_lon": r.target_lon,
                "project_lat": r.target_lat,
                "project_coordinates": r.project_coordinates,
            }
        )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OVKML -> ProjectAudit CSV 转换工具")
    parser.add_argument("--input", required=True, help="输入 OVKML/KML 文件路径")
    parser.add_argument("--output-dir", default=".", help="输出目录，默认当前目录")
    parser.add_argument(
        "--input-crs",
        choices=["wgs84", "cgcs2000"],
        default="wgs84",
        help="输入坐标系，默认 wgs84",
    )
    parser.add_argument(
        "--output-crs",
        choices=["wgs84", "cgcs2000", "cgcs2000_proj"],
        default="cgcs2000",
        help="输出坐标系，默认 cgcs2000",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] 输入文件不存在: {input_path}", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        tree = ET.parse(input_path)
    except ET.ParseError as e:
        print(f"[ERROR] XML 解析失败: {e}", file=sys.stderr)
        return 3

    root = tree.getroot()
    transformer = CoordinateTransformer(args.input_crs, args.output_crs)
    records: List[PlacemarkRecord] = []

    walk_kml(root, [], records, transformer)

    if not records:
        print("[WARN] 未提取到 Placemark。请检查文件结构或命名空间。")

    stem = input_path.stem
    project_csv = output_dir / f"{stem}_projectaudit.csv"
    detail_csv = output_dir / f"{stem}_detail.csv"
    preview_json = output_dir / f"{stem}_preview.json"

    write_projectaudit_csv(project_csv, records)
    write_detail_csv(detail_csv, records)
    write_preview_json(preview_json, records)

    print(f"[OK] Placemark 数量: {len(records)}")
    print(f"[OK] ProjectAudit 导入文件: {project_csv}")
    print(f"[OK] 详细核查文件: {detail_csv}")
    print(f"[OK] 预览文件: {preview_json}")

    if args.output_crs == "cgcs2000_proj":
        print("[NOTE] project_lon/project_lat 仍输出经纬度（便于导入 ProjectAudit），")
        print("       投影坐标（米）请使用 detail 文件中的 cgcs2000_x/cgcs2000_y。")

    if Transformer is None and (args.input_crs != args.output_crs or args.output_crs == "cgcs2000_proj"):
        print("[WARN] 未检测到 pyproj：geodetic 转换按近似直通处理；投影模式将失败。", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
