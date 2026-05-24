"""
core/utils_watermark.py

文物现场采集照片水印工具
---------------------------------------------------
• 在照片右下角合成"明水印"
• 水印内容：文物名称 / 经度(度分秒) / 纬度(度分秒) / 采集时间 / 采集单位
• 背景：半透明黑色圆角矩形，防止白底照片看不清文字
• 字体：优先加载系统中文字体（Windows / Linux 均兼容），
        不可用时退回 Pillow 默认字体
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from io import BytesIO
from typing import Union

from PIL import Image, ImageDraw, ImageFont

# ── 中文字体候选路径（按优先级排列）────────────────────────────
_FONT_CANDIDATES: list[str] = [
    # Windows
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    # Linux（常见 CJK 字体）
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # macOS
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """按优先级加载支持中文的字体，都失败则用 Pillow 内置字体。"""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 最后兜底：Pillow 内置位图字体（不支持中文，但不会崩溃）
    return ImageFont.load_default()


def decimal_to_dms(decimal_deg: float, is_longitude: bool = True) -> str:
    """
    将十进制度转换为度分秒字符串。

    示例：
        decimal_to_dms(90.335, is_longitude=True)  → '东经 90°20′06.00″'
        decimal_to_dms(43.435, is_longitude=False) → '北纬 43°26′06.00″'
    """
    if is_longitude:
        direction = "东经" if decimal_deg >= 0 else "西经"
    else:
        direction = "北纬" if decimal_deg >= 0 else "南纬"

    abs_deg = abs(decimal_deg)
    degrees = int(abs_deg)
    minutes_float = (abs_deg - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60

    return f"{direction} {degrees}°{minutes:02d}′{seconds:05.2f}″"


def add_heritage_watermark(
    image_source: Union[str, bytes, BytesIO],
    heritage_name: str,
    collected_at: datetime,
    longitude: float,
    latitude: float,
    collect_unit: str = "文物管理部门",
) -> Image.Image:
    """
    在照片右下角合成文物采集水印，返回 PIL.Image（RGB 模式）。

    参数
    ----
    image_source   : 原始图片——文件路径、bytes 或 BytesIO 均可
    heritage_name  : 文物名称
    collected_at   : 采集时间（datetime 对象）
    longitude      : 十进制经度（float / Decimal 均可）
    latitude       : 十进制纬度（float / Decimal 均可）
    collect_unit   : 采集单位名称（可由 settings.HERITAGE_COLLECT_UNIT 注入）

    返回
    ----
    PIL.Image（RGB），可直接 .save() 为 JPEG
    """
    lon = float(longitude)
    lat = float(latitude)
    lon_dms = decimal_to_dms(lon, is_longitude=True)
    lat_dms = decimal_to_dms(lat, is_longitude=False)
    time_str = collected_at.strftime("%Y-%m-%d %H:%M:%S")

    watermark_lines = [
        f"文物名称：{heritage_name}",
        f"经　　度：{lon_dms}",
        f"纬　　度：{lat_dms}",
        f"采集时间：{time_str}",
        f"采集单位：{collect_unit}",
    ]

    # ── 打开原图，转 RGBA 以支持透明合成 ──────────────────────
    img = Image.open(image_source)
    # 修正 EXIF 旋转方向
    img = _fix_image_orientation(img)
    img = img.convert("RGBA")
    img_w, img_h = img.size

    # ── 字体大小随图片宽度自适应（短边基准，最小 20px）─────────
    base = min(img_w, img_h)
    font_size = max(20, int(base * 0.030))
    font = _load_font(font_size)

    # ── 测量每行文字尺寸 ─────────────────────────────────────
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    line_sizes: list[tuple[int, int]] = []
    for line in watermark_lines:
        bbox = probe.textbbox((0, 0), line, font=font)
        line_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

    padding = int(font_size * 0.7)          # 内边距
    line_gap = int(font_size * 0.35)        # 行间距
    box_w = max(w for w, _ in line_sizes) + padding * 2
    box_h = sum(h for _, h in line_sizes) + line_gap * (len(watermark_lines) - 1) + padding * 2

    margin = int(base * 0.025)              # 距图片边缘距离
    x0 = img_w - box_w - margin
    y0 = img_h - box_h - margin

    # 防止水印超出画面左边界（极宽图片）
    x0 = max(margin, x0)

    # ── 绘制半透明黑色圆角背景 ───────────────────────────────
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    corner_r = int(font_size * 0.5)
    ov_draw.rounded_rectangle(
        [x0, y0, x0 + box_w, y0 + box_h],
        radius=corner_r,
        fill=(0, 0, 0, 168),            # 透明度 ≈ 66%
    )
    img = Image.alpha_composite(img, overlay)

    # ── 绘制白色文字（带 1px 灰色描边增强可读性）───────────────
    draw = ImageDraw.Draw(img)
    y_cursor = y0 + padding
    for i, (line, (lw, lh)) in enumerate(zip(watermark_lines, line_sizes)):
        tx = x0 + padding
        # 1px 轮廓（深灰）
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            draw.text((tx + dx, y_cursor + dy), line, font=font, fill=(60, 60, 60, 200))
        # 主体文字（亮白）
        draw.text((tx, y_cursor), line, font=font, fill=(255, 255, 255, 245))
        y_cursor += lh + line_gap

    return img.convert("RGB")


def _fix_image_orientation(img: Image.Image) -> Image.Image:
    """根据 EXIF Orientation 标签自动旋转图片，避免手机竖拍照片横置。"""
    try:
        exif = img._getexif()  # type: ignore[attr-defined]
        if exif is None:
            return img
        orientation_tag = 274  # EXIF Orientation
        orientation = exif.get(orientation_tag, 1)
        rotation_map = {3: 180, 6: 270, 8: 90}
        if orientation in rotation_map:
            img = img.rotate(rotation_map[orientation], expand=True)
    except Exception:
        pass
    return img
