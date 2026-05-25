"""DEM 网格化增量缓存处理工具。

功能目标：
1. 根据经纬度定位到 1° x 1° 的标准 SRTM 瓦片；
2. 本地存在则直接高性能采样；
3. 本地不存在时按需调用 OpenTopography 下载后缓存；
4. 任意失败都平滑降级为 None，避免影响主业务流程。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import threading
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from django.conf import settings

try:
    import rasterio
    from rasterio.errors import RasterioIOError
except Exception:  # pragma: no cover - 运行环境缺少 rasterio 时兜底
    rasterio = None
    RasterioIOError = Exception


logger = logging.getLogger(__name__)

OPENTOPO_GLOBAL_DEM_API = "https://portal.opentopography.org/API/globaldem"
DEFAULT_DEM_TYPE = "SRTMGL1"  # SRTM 30m
REQUEST_TIMEOUT_SECONDS = 15
INVALID_ELEVATION_SENTINELS = {-32768.0, -32767.0}

# 防止并发请求同一瓦片时重复下载。
_TILE_LOCKS: dict[str, threading.Lock] = {}
_TILE_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class DemTileSpec:
    """表示一个 1° x 1° DEM 瓦片范围。"""

    tile_name: str
    west: int
    east: int
    south: int
    north: int


def _get_tile_lock(tile_key: str) -> threading.Lock:
    with _TILE_LOCKS_GUARD:
        lock = _TILE_LOCKS.get(tile_key)
        if lock is None:
            lock = threading.Lock()
            _TILE_LOCKS[tile_key] = lock
        return lock


def build_tile_spec(longitude: float, latitude: float) -> DemTileSpec:
    """将经纬度映射到标准全球网格瓦片，例如 N42E089。"""
    west = math.floor(longitude)
    south = math.floor(latitude)
    east = west + 1
    north = south + 1

    lat_prefix = "N" if south >= 0 else "S"
    lon_prefix = "E" if west >= 0 else "W"
    tile_name = f"{lat_prefix}{abs(south):02d}{lon_prefix}{abs(west):03d}"

    return DemTileSpec(
        tile_name=tile_name,
        west=west,
        east=east,
        south=south,
        north=north,
    )


def _dem_root_dir() -> Path:
    configured = str(getattr(settings, "DEM_TILES_DIR", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    fallback = Path(settings.BASE_DIR) / "dem_tiles"
    logger.warning("DEM_TILES_DIR 未配置，自动回退到默认目录: %s", fallback)
    return fallback


def _build_tile_path(tile_spec: DemTileSpec, dem_type: str = DEFAULT_DEM_TYPE) -> Path:
    return _dem_root_dir() / dem_type / f"{tile_spec.tile_name}.tif"


def _build_request_proxies(request_url: str) -> Optional[dict[str, str]]:
    """构造当前请求使用的局部代理配置（不污染全局环境）。

    说明：
    1) 仅在本次 requests.get 生命周期内通过 proxies 参数生效；
    2) 默认仅对 OpenTopography 域名生效，避免影响其他业务请求；
    3) 兼容 SOCKS5 与 HTTP 代理协议。

    常用 settings 配置建议：
        DEM_DOWNLOAD_PROXY_ENABLED = True
        DEM_DOWNLOAD_PROXY_SCHEME = 'socks5'   # 可切换为 'http'
        DEM_DOWNLOAD_PROXY_HOST = '127.0.0.1'
        DEM_DOWNLOAD_PROXY_PORT = 10808
        DEM_DOWNLOAD_PROXY_ONLY_DOMAINS = ('portal.opentopography.org',)

    SOCKS5 注意：
        若使用 socks5://，需要安装依赖：pip install "requests[socks]"
    """
    enabled = bool(getattr(settings, "DEM_DOWNLOAD_PROXY_ENABLED", False))
    if not enabled:
        return None

    parsed = urlparse(request_url)
    target_host = (parsed.hostname or "").lower()
    only_domains = tuple(
        str(item).strip().lower()
        for item in getattr(settings, "DEM_DOWNLOAD_PROXY_ONLY_DOMAINS", ("portal.opentopography.org",))
        if str(item).strip()
    )

    if only_domains and not any(target_host == d or target_host.endswith(f".{d}") for d in only_domains):
        return None

    scheme = str(getattr(settings, "DEM_DOWNLOAD_PROXY_SCHEME", "socks5")).strip().lower() or "socks5"
    host = str(getattr(settings, "DEM_DOWNLOAD_PROXY_HOST", "127.0.0.1")).strip() or "127.0.0.1"
    port = int(getattr(settings, "DEM_DOWNLOAD_PROXY_PORT", 10808))

    # 示例（SOCKS5）：
    # proxies = {
    #     'http': 'socks5://127.0.0.1:10808',
    #     'https': 'socks5://127.0.0.1:10808'
    # }
    # 若本地代理是 HTTP 端口，则将 scheme 改为 'http' 即可。
    proxy_url = f"{scheme}://{host}:{port}"
    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def _download_tile(tile_spec: DemTileSpec, destination: Path, dem_type: str = DEFAULT_DEM_TYPE) -> bool:
    """通过 OpenTopography 按 1° 网格下载 GeoTIFF 并落盘缓存。"""
    api_key = str(getattr(settings, "OPENTOPO_API_KEY", "")).strip()
    if not api_key:
        logger.warning("OPENTOPO_API_KEY 未配置，无法自动下载 DEM 瓦片: %s", tile_spec.tile_name)
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".part")

    params = {
        "demtype": dem_type,
        "south": tile_spec.south,
        "north": tile_spec.north,
        "west": tile_spec.west,
        "east": tile_spec.east,
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    proxies = _build_request_proxies(OPENTOPO_GLOBAL_DEM_API)

    def _stream_download(active_proxies: Optional[dict[str, str]]) -> None:
        with requests.get(
            OPENTOPO_GLOBAL_DEM_API,
            params=params,
            stream=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            proxies=active_proxies,
        ) as response:
            response.raise_for_status()

            with open(temp_path, "wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)

    try:
        # 先走局部代理，若代理不可用再自动回退一次直连，提升可用性。
        try:
            _stream_download(proxies)
        except requests.RequestException as proxy_exc:
            if proxies:
                logger.warning(
                    "DEM 代理下载失败，回退直连重试。tile=%s, proxy=%s, err=%s",
                    tile_spec.tile_name,
                    proxies.get("https"),
                    proxy_exc,
                )
                _stream_download(None)
            else:
                raise

        if not temp_path.exists() or temp_path.stat().st_size == 0:
            logger.error("DEM 瓦片下载结果为空: %s", tile_spec.tile_name)
            return False

        temp_path.replace(destination)
        logger.info("DEM 瓦片下载成功并已缓存: %s", destination)
        return True

    except requests.RequestException as exc:
        logger.exception("DEM 瓦片下载失败(%s): %s", tile_spec.tile_name, exc)
        return False
    except OSError as exc:
        logger.exception("DEM 瓦片写入失败(%s): %s", tile_spec.tile_name, exc)
        return False
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def ensure_tile_cached(longitude: float, latitude: float, dem_type: str = DEFAULT_DEM_TYPE) -> Optional[Path]:
    """确保目标瓦片已缓存，返回本地路径；失败时返回 None。"""
    tile_spec = build_tile_spec(longitude, latitude)
    tile_path = _build_tile_path(tile_spec, dem_type)

    if tile_path.exists():
        return tile_path

    tile_lock = _get_tile_lock(str(tile_path))
    with tile_lock:
        # 双重检查，避免锁竞争期间重复下载。
        if tile_path.exists():
            return tile_path

        ok = _download_tile(tile_spec=tile_spec, destination=tile_path, dem_type=dem_type)
        if not ok:
            return None

    return tile_path if tile_path.exists() else None


def _clean_elevation(value: float, nodata: Optional[float]) -> Optional[float]:
    """清洗 DEM 异常值（海洋、无信号、坏值）。"""
    if value != value:  # NaN
        return None

    if nodata is not None and abs(value - nodata) < 1e-6:
        return None

    if value in INVALID_ELEVATION_SENTINELS:
        return None

    # 低于 -10000 通常为无效栅格编码，非真实海拔。
    if value <= -10000:
        return None

    # 超过地球合理高程范围视为坏值。
    if value > 9000:
        return None

    return round(value, 2)


def sample_tile_elevation(tile_path: Path, longitude: float, latitude: float) -> Optional[float]:
    """从 GeoTIFF 中采样指定经纬度高程。"""
    if rasterio is None:
        logger.error("rasterio 未安装，无法执行 DEM 栅格采样")
        return None

    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="TRUE"):
            with rasterio.open(tile_path, mode="r", sharing=True) as dataset:
                bounds = dataset.bounds
                # 先做边界保护，避免边缘点触发越界读取。
                if not (bounds.left <= longitude <= bounds.right and bounds.bottom <= latitude <= bounds.top):
                    logger.warning("坐标超出瓦片边界，tile=%s, lon=%s, lat=%s", tile_path, longitude, latitude)
                    return None

                sampled = next(dataset.sample([(longitude, latitude)]), None)
                if sampled is None or len(sampled) == 0:
                    return None

                raw_value = float(sampled[0])
                return _clean_elevation(raw_value, dataset.nodata)

    except (RasterioIOError, ValueError, StopIteration) as exc:
        logger.exception("DEM 采样失败(%s): %s", tile_path, exc)
        return None


def get_dem_elevation(longitude: float, latitude: float, dem_type: str = DEFAULT_DEM_TYPE) -> Optional[float]:
    """外部统一调用入口：按需下载 + 缓存 + 高程反查。"""
    try:
        lon = float(longitude)
        lat = float(latitude)
    except (TypeError, ValueError):
        logger.warning("DEM 反查参数非法: lon=%s, lat=%s", longitude, latitude)
        return None

    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        logger.warning("DEM 反查参数越界: lon=%s, lat=%s", lon, lat)
        return None

    tile_path = ensure_tile_cached(longitude=lon, latitude=lat, dem_type=dem_type)
    if tile_path is None:
        return None

    return sample_tile_elevation(tile_path=tile_path, longitude=lon, latitude=lat)


def describe_tile(longitude: float, latitude: float) -> str:
    """用于调试输出：返回坐标对应的瓦片名。"""
    return build_tile_spec(longitude, latitude).tile_name
