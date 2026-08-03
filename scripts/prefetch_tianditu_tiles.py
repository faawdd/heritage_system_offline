#!/usr/bin/env python3
"""Prefetch TianDiTu WMTS tiles for offline desktop packaging.

Default behavior:
- Region: Turpan (configurable via env or CLI)
- Layers: img, cia, vec, cva, ter, cta
- Zoom levels: 0-13 (configurable)
- Output: static/tiles/tianditu/<layer>/<z>/<x>/<y>.png
"""

from __future__ import annotations

import argparse
import concurrent.futures
import math
import os
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence, Tuple

import requests

DEFAULT_TDT_TK = "424ac2af85564078477428c1a2b72018"
DEFAULT_LAYERS = ("img", "cia", "vec", "cva", "ter", "cta")
# Turpan bounding box (rough administrative coverage)
DEFAULT_BBOX = (87.0, 40.8, 92.2, 43.9)  # west, south, east, north
DEFAULT_ZOOM_MIN = 0
DEFAULT_ZOOM_MAX = 13
DEFAULT_CONCURRENCY = 16
DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 3
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def lon_to_tile_x(lon: float, z: int) -> int:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    return max(0, min(n - 1, x))


def lat_to_tile_y(lat: float, z: int) -> int:
    # WebMercator clamp
    lat = max(-85.05112878, min(85.05112878, lat))
    n = 2 ** z
    rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, y))


def tile_ranges_for_bbox(bbox: Tuple[float, float, float, float], z: int) -> Tuple[range, range]:
    west, south, east, north = bbox
    min_x = lon_to_tile_x(west, z)
    max_x = lon_to_tile_x(east, z)
    # y grows southward, so north is min y and south is max y
    min_y = lat_to_tile_y(north, z)
    max_y = lat_to_tile_y(south, z)
    if min_x > max_x:
        min_x, max_x = max_x, min_x
    if min_y > max_y:
        min_y, max_y = max_y, min_y
    return range(min_x, max_x + 1), range(min_y, max_y + 1)


def build_url(layer: str, z: int, x: int, y: int, tk: str) -> str:
    host = (x + y) % 8
    return (
        f"https://t{host}.tianditu.gov.cn/{layer}_w/wmts"
        f"?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        f"&LAYER={layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
        f"&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk={tk}"
    )


def build_tasks(
    layers: Sequence[str],
    zoom_min: int,
    zoom_max: int,
    bbox: Tuple[float, float, float, float],
) -> Iterator[Tuple[str, int, int, int]]:
    for layer in layers:
        for z in range(zoom_min, zoom_max + 1):
            x_range, y_range = tile_ranges_for_bbox(bbox, z)
            for x in x_range:
                for y in y_range:
                    yield (layer, z, x, y)


def download_one(
    task: Tuple[str, int, int, int],
    output_dir: Path,
    token: str,
    timeout_sec: int,
    retries: int,
    user_agent: str,
) -> Tuple[str, bool, str]:
    layer, z, x, y = task
    target = output_dir / layer / str(z) / str(x) / f"{y}.png"

    if target.exists() and target.stat().st_size > 0:
        return (f"{layer}/{z}/{x}/{y}", True, "cached")

    target.parent.mkdir(parents=True, exist_ok=True)
    url = build_url(layer, z, x, y, token)
    headers = {
        "User-Agent": user_agent,
        "Referer": "http://lbs.tianditu.gov.cn/home.html",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    last_error = ""
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout_sec)
            if response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                continue
            content = response.content
            if not content:
                last_error = "empty response"
                continue
            target.write_bytes(content)
            return (f"{layer}/{z}/{x}/{y}", True, "downloaded")
        except requests.RequestException as exc:
            last_error = str(exc)

    return (f"{layer}/{z}/{x}/{y}", False, last_error or "unknown error")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prefetch TianDiTu tiles for offline package")
    parser.add_argument("--output-dir", default="static/tiles/tianditu", help="Output tile root directory")
    parser.add_argument("--layers", default=env_or_default("TDT_PREFETCH_LAYERS", ",".join(DEFAULT_LAYERS)))
    parser.add_argument("--zoom-min", type=int, default=int(env_or_default("TDT_PREFETCH_ZOOM_MIN", str(DEFAULT_ZOOM_MIN))))
    parser.add_argument("--zoom-max", type=int, default=int(env_or_default("TDT_PREFETCH_ZOOM_MAX", str(DEFAULT_ZOOM_MAX))))
    parser.add_argument("--west", type=float, default=float(env_or_default("TDT_PREFETCH_WEST", str(DEFAULT_BBOX[0]))))
    parser.add_argument("--south", type=float, default=float(env_or_default("TDT_PREFETCH_SOUTH", str(DEFAULT_BBOX[1]))))
    parser.add_argument("--east", type=float, default=float(env_or_default("TDT_PREFETCH_EAST", str(DEFAULT_BBOX[2]))))
    parser.add_argument("--north", type=float, default=float(env_or_default("TDT_PREFETCH_NORTH", str(DEFAULT_BBOX[3]))))
    parser.add_argument("--concurrency", type=int, default=int(env_or_default("TDT_PREFETCH_CONCURRENCY", str(DEFAULT_CONCURRENCY))))
    parser.add_argument("--timeout", type=int, default=int(env_or_default("TDT_PREFETCH_TIMEOUT", str(DEFAULT_TIMEOUT))))
    parser.add_argument("--retries", type=int, default=int(env_or_default("TDT_PREFETCH_RETRIES", str(DEFAULT_RETRIES))))
    parser.add_argument("--token", default=env_or_default("VITE_TDT_TK", env_or_default("TDT_TK", DEFAULT_TDT_TK)))
    parser.add_argument("--user-agent", default=env_or_default("TDT_PREFETCH_USER_AGENT", DEFAULT_USER_AGENT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.zoom_min < 0 or args.zoom_max < args.zoom_min:
        print("[tdt-prefetch] invalid zoom range")
        return 2
    if args.west >= args.east or args.south >= args.north:
        print("[tdt-prefetch] invalid bbox")
        return 2

    output_dir = Path(args.output_dir).resolve()
    layers = [item.strip() for item in str(args.layers).split(",") if item.strip()]
    bbox = (args.west, args.south, args.east, args.north)

    task_list = list(build_tasks(layers, args.zoom_min, args.zoom_max, bbox))
    total = len(task_list)
    print(
        "[tdt-prefetch] start",
        f"layers={layers}",
        f"zoom={args.zoom_min}-{args.zoom_max}",
        f"bbox={bbox}",
        f"tiles={total}",
        f"output={output_dir}",
    )

    if total == 0:
        print("[tdt-prefetch] no tiles to download")
        return 0

    ok_count = 0
    fail_count = 0
    cached_count = 0
    failed_samples: List[str] = []

    max_workers = max(1, min(64, int(args.concurrency)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                download_one,
                task,
                output_dir,
                args.token,
                int(args.timeout),
                int(args.retries),
                args.user_agent,
            )
            for task in task_list
        ]

        done = 0
        for future in concurrent.futures.as_completed(futures):
            key, ok, status = future.result()
            done += 1
            if ok:
                ok_count += 1
                if status == "cached":
                    cached_count += 1
            else:
                fail_count += 1
                if len(failed_samples) < 20:
                    failed_samples.append(f"{key}: {status}")

            if done % 500 == 0 or done == total:
                print(f"[tdt-prefetch] progress {done}/{total} ok={ok_count} fail={fail_count} cached={cached_count}")

    print(f"[tdt-prefetch] done ok={ok_count} fail={fail_count} cached={cached_count} total={total}")
    if fail_count > 0:
        print("[tdt-prefetch] failed samples:")
        for line in failed_samples:
            print("  -", line)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
