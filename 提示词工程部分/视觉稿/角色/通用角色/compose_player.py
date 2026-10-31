#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把泰拉瑞亚风格角色合成进雪地场景，检验占屏比例与融合度。

    A  640×360 逻辑 + 40×56 角色 ×1 → 1920×1080（泰拉瑞亚原始比例）
    B  960×540 逻辑 + 40×56 角色 ×2 → 1920×1080（放大一档便于观察）

用法
    python compose_player.py --scene <背景图> --outdir ./
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from player_parts import render as render_parts  # noqa: E402

OUTLINE = (18, 22, 30)


def add_outline(sprite, color=OUTLINE):
    alpha = sprite.split()[3]
    grown = alpha.filter(ImageFilter.MaxFilter(3))
    ring = Image.new("RGBA", sprite.size, color + (255,))
    ring.putalpha(grown)
    ring.paste(sprite, (0, 0), sprite)
    return ring


def grade(sprite, ambient=(0.76, 0.82, 0.94), sat=0.70):
    px = sprite.load()
    w, h = sprite.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            r = lum + (r - lum) * sat
            g = lum + (g - lum) * sat
            b = lum + (b - lum) * sat
            px[x, y] = (int(min(255, r * ambient[0])),
                        int(min(255, g * ambient[1])),
                        int(min(255, b * ambient[2])), a)
    return sprite


def pixelize(img, size, colors):
    small = img.convert("RGB").resize(size, Image.BOX)
    return small.quantize(colors=colors, method=Image.MEDIANCUT,
                          dither=Image.NONE).convert("RGB")


def compose(scene, logical, scale, colors, out_path, pos=(0.44, 0.88)):
    base = pixelize(Image.open(scene), logical, colors)
    W, H = logical

    sprite = grade(render_parts(1, True))
    if scale != 1:
        sprite = sprite.resize((sprite.width * scale, sprite.height * scale),
                               Image.NEAREST)
    sw, sh = sprite.size
    px = int(W * pos[0])
    py = int(H * pos[1]) - sh

    shadow = Image.new("RGBA", (sw, 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(shadow)
    d.ellipse([3, 2, sw - 3, 9], fill=(6, 10, 16, 110))
    base.paste(shadow, (px, py + sh - 4), shadow)
    base.paste(sprite, (px, py), sprite)

    out = base.resize((W * 3, H * 3), Image.NEAREST) if logical == (640, 360) \
        else base.resize((W * 2, H * 2), Image.NEAREST)
    out.save(out_path)
    return out.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    a = compose(args.scene, (640, 360), 1, 32, out / "player_A_640.png")
    print(f"[ok] player_A_640.png  {a}  角色 40×56 @1×")
    b = compose(args.scene, (960, 540), 2, 40, out / "player_B_960.png")
    print(f"[ok] player_B_960.png  {b}  角色 40×56 @2×")


if __name__ == "__main__":
    main()
