#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 CC0 角色素材接进项目：抽帧 → 统一规范 → 合成演示。

素材：MoikMellah《MV Platformer Male (32x64)》，CC0（公有领域）
    https://opengameart.org/content/mv-platformer-male-32x64
    文件：maleBase/full/advnt_full.png（320×640，10×10 格，每格 32×64）

帧位（实测）：
    待机  0-0
    行走  1-0 … 1-4（5 帧）
    跳跃  1-7 … 1-9（3 帧）

产出：
    player_idle.png    32×64 单帧
    player_walk.png    192×64（6 帧横排，含待机首帧）
    player_jump.png     96×64（3 帧横排）
    scene_cc0.png      1920×1080 场景合成
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

CW, CH = 32, 64
BASE = Path(__file__).resolve().parent
SHEET = BASE.parents[3] / "assets" / "characters" / \
    "cc0_mv_platformer_male" / "maleBase" / "full" / "advnt_full.png"

FRAMES = {
    "idle": [(0, 0)],
    "walk": [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)],
    "jump": [(1, 7), (1, 8), (1, 9)],
}


def cell(sheet, row, col):
    return sheet.crop((col * CW, row * CH, (col + 1) * CW, (row + 1) * CH))


def strip(sheet, coords, pad_frames=0):
    frames = [cell(sheet, r, c) for r, c in coords]
    total = len(frames) + pad_frames
    out = Image.new("RGBA", (CW * total, CH), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.paste(f, (i * CW, 0))
    return out


def grade(sprite, ambient=(0.78, 0.84, 0.95), sat=0.72):
    px = sprite.load()
    for y in range(sprite.height):
        for x in range(sprite.width):
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


def compose(scene_path, out_path, scale=2, logical=(960, 540), pos=(0.44, 0.90)):
    base = pixelize(Image.open(scene_path), logical, 40)
    W, H = logical
    sprite = grade(cell(Image.open(SHEET).convert("RGBA"), 1, 2))  # 迈步中段
    if scale != 1:
        sprite = sprite.resize((CW * scale, CH * scale), Image.NEAREST)
    sw, sh = sprite.size
    px = int(W * pos[0])
    py = int(H * pos[1]) - sh

    shadow = Image.new("RGBA", (sw, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(shadow)
    d.ellipse([3, 3, sw - 3, 11], fill=(6, 10, 16, 110))
    base.paste(shadow, (px, py + sh - 6), shadow)
    base.paste(sprite, (px, py), sprite)

    out = base.resize((W * 2, H * 2), Image.NEAREST)
    out.save(out_path)
    return out.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    sheet = Image.open(SHEET).convert("RGBA")
    strip(sheet, FRAMES["idle"]).save(out / "player_idle.png")
    strip(sheet, FRAMES["idle"] + FRAMES["walk"], 0).save(out / "player_walk.png")
    strip(sheet, FRAMES["jump"]).save(out / "player_jump.png")
    print("[ok] player_idle.png / player_walk.png / player_jump.png")

    size = compose(args.scene, out / "scene_cc0.png")
    print(f"[ok] scene_cc0.png {size}")

    # 帧条预览
    for name in ("player_walk", "player_jump"):
        im = Image.open(out / f"{name}.png")
        big = im.resize((im.width * 5, im.height * 5), Image.NEAREST)
        bg = Image.new("RGB", (big.width + 20, big.height + 20), (24, 32, 44))
        bg.paste(big, (10, 10), big)
        bg.save(out / f"{name}_big.png")
    print("[ok] 帧条预览 *_big.png")


if __name__ == "__main__":
    main()
