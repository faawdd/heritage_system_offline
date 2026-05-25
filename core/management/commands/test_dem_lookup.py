"""管理命令：DEM 自动下载 + 海拔反查测试。

示例：
python manage.py test_dem_lookup --lon 89.2451 --lat 42.8123
"""

from django.core.management.base import BaseCommand, CommandError

from utils.dem_handler import build_tile_spec, get_dem_elevation


class Command(BaseCommand):
    help = "测试指定经纬度的 DEM 瓦片自动下载与海拔反查"

    def add_arguments(self, parser):
        parser.add_argument("--lon", required=True, type=float, help="经度，例如 89.2451")
        parser.add_argument("--lat", required=True, type=float, help="纬度，例如 42.8123")

    def handle(self, *args, **options):
        lon = options["lon"]
        lat = options["lat"]

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise CommandError("经纬度超出有效范围：lon 必须在 [-180,180]，lat 必须在 [-90,90]")

        tile = build_tile_spec(lon, lat)
        self.stdout.write(self.style.NOTICE("开始执行 DEM 反查测试..."))
        self.stdout.write(f"输入坐标: lon={lon}, lat={lat}")
        self.stdout.write(
            f"命中网格: {tile.tile_name} (west={tile.west}, east={tile.east}, south={tile.south}, north={tile.north})"
        )

        elevation = get_dem_elevation(lon, lat)
        if elevation is None:
            self.stdout.write(
                self.style.WARNING(
                    "反查结果为空(None)。可能原因：网络超时/API 不可用/海洋无信号/本机未安装 rasterio。"
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"反查成功，高程: {elevation} 米"))
