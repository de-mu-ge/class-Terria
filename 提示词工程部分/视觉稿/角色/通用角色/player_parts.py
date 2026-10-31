#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泰拉瑞亚风格角色 · 48×64（v3，按参考稿实测比例重排）。

从参考图量出来的比例（总高约 62）：
    头（含发）2–28 → 占全身 43%，脸只是头里的一小块 (18,14)-(31,28)
    躯干 30–42，两臂向外张，末端到胯部；腿 48–57，中间留缝；靴 57–61

配色照参考改：裤子灰蓝、上衣浅灰、靴深棕、背包蓝灰。

部件坐标都在 draw_parts() 里，逐条可改。
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H = 48, 64

C = {
    "hair": (150, 62, 42),
    "hair_d": (104, 40, 28),
    "hair_l": (196, 96, 62),
    "skin": (244, 156, 108),
    "skin_d": (200, 112, 78),
    "eye_w": (252, 250, 246),
    "eye_k": (36, 26, 26),
    "shirt": (206, 204, 190),
    "shirt_d": (164, 162, 148),
    "pants": (126, 138, 164),
    "pants_d": (96, 106, 130),
    "boot": (104, 66, 40),
    "boot_d": (70, 44, 26),
    "bag": (116, 138, 184),
    "bag_d": (82, 100, 142),
    "belt": (108, 84, 56),
    "outline": (30, 21, 19),
}


def draw_parts():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def r(x0, y0, x1, y1, key):
        d.rectangle([x0, y0, x1, y1], fill=C[key] + (255,))

    # —— 背包（身后，先画）——
    r(7, 28, 14, 46, "bag")
    r(7, 28, 9, 46, "bag_d")
    r(10, 31, 13, 34, "bag_d")
    r(10, 39, 13, 41, "bag_d")

    # —— 头发主体（宽过头，锯齿顶）——
    r(10, 6, 34, 27, "hair")
    for x0, y0, x1, y1 in [
        (10, 2, 13, 7), (14, 0, 17, 6), (18, 2, 21, 7),
        (22, 0, 25, 5), (26, 2, 29, 7), (30, 4, 33, 9),
        (8, 16, 11, 30), (33, 14, 36, 28),
    ]:
        r(x0, y0, x1, y1, "hair")
    r(13, 8, 18, 9, "hair_l")
    r(22, 5, 27, 6, "hair_l")
    r(28, 9, 31, 10, "hair_d")
    r(11, 18, 13, 26, "hair_d")

    # —— 脸（只占头里的一小块）——
    r(18, 14, 31, 28, "skin")
    r(18, 26, 31, 28, "skin_d")

    # —— 刘海 ——
    r(10, 6, 34, 15, "hair")
    r(18, 14, 22, 16, "hair")

    # —— 单眼 + 眉 ——
    r(22, 18, 26, 22, "eye_w")
    r(24, 19, 25, 21, "eye_k")
    r(21, 17, 27, 17, "hair_d")

    # —— 嘴 / 腮红 ——
    r(24, 25, 26, 25, "eye_k")
    r(19, 23, 20, 24, "skin_d")

    # —— 脖子 ——
    r(22, 28, 27, 30, "skin_d")

    # —— 躯干 ——
    r(16, 30, 31, 40, "shirt")
    r(16, 38, 31, 40, "shirt_d")
    r(16, 40, 31, 42, "belt")

    # —— 肩口袖子 ——
    r(12, 30, 16, 34, "shirt")
    r(31, 30, 35, 34, "shirt")

    # —— 裸手臂 ——
    r(11, 34, 15, 43, "skin")
    r(32, 34, 36, 43, "skin")
    r(11, 41, 15, 43, "skin_d")
    r(32, 41, 36, 43, "skin_d")

    # —— 胯 / 裤 ——
    r(17, 42, 30, 48, "pants")
    r(17, 42, 19, 48, "pants_d")

    # —— 双腿（中间留缝）——
    r(18, 48, 23, 57, "pants")
    r(25, 48, 30, 57, "pants")
    r(18, 54, 23, 57, "pants_d")
    r(25, 54, 30, 57, "pants_d")

    # —— 靴 ——
    r(16, 57, 24, 61, "boot")
    r(24, 57, 32, 61, "boot")
    r(16, 60, 24, 61, "boot_d")
    r(24, 60, 32, 61, "boot_d")

    return img


def outline(sprite, color=C["outline"]):
    alpha = sprite.split()[3]
    grown = alpha.filter(ImageFilter.MaxFilter(3))
    ring = Image.new("RGBA", sprite.size, color + (255,))
    ring.putalpha(grown)
    ring.paste(sprite, (0, 0), sprite)
    return ring


def render(scale=1, with_outline=True):
    img = draw_parts()
    if with_outline:
        img = outline(img)
    if scale != 1:
        img = img.resize((W * scale, H * scale), Image.NEAREST)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--scale", type=int, default=10)
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    fig = render(args.scale)
    sheet = Image.new("RGB", (W * args.scale + 40, H * args.scale + 20),
                      (24, 32, 44))
    sheet.paste(fig, (20, 10), fig)
    sheet.save(out / "player_parts.png")
    print(f"[ok] player_parts.png ({sheet.width}×{sheet.height})")


if __name__ == "__main__":
    main()
