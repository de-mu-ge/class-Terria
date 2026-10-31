#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把千早爱音合成进高精度场景 —— v2。

第一版的教训：
  1. 48×64 贴在 2560×1440 的图上，像素密度差一档，像剪贴画；
  2. 人物高饱和粉 / 白 / 绿，与场景的冷灰蓝不在同一个光环境里。

本版做法：
  · Sprint 直接按 96×128 原生绘制（不是 48×64 放大）；
  · 合成前对环境光染色（降饱和 + 冷色偏移），让角色"站进"场景里；
  · 960×540 逻辑画布 ×2 = 1920×1080。

用法：
    python compose_scene.py --scene <背景图> --outdir ./
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 调色板 ----
HAIR = (240, 163, 184)
HAIR_D = (198, 118, 138)
HAIR_DD = (160, 88, 106)
HAIR_L = (255, 202, 216)
SKIN = (247, 223, 201)
SKIN_D = (222, 186, 160)
SKIN_L = (252, 234, 217)
EYE = (140, 147, 160)
EYE_D = (86, 93, 106)
EYE_L = (206, 212, 221)
WHITE = (255, 255, 255)
SHIRT = (248, 248, 250)
SHIRT_D = (216, 220, 227)
COAT = (199, 204, 212)
COAT_D = (158, 164, 175)
COAT_L = (232, 236, 242)
TIE = (78, 140, 90)
TIE_D = (48, 92, 58)
SKIRT = (62, 122, 78)
SKIRT_D = (38, 82, 52)
SOCK = (78, 140, 90)
SOCK_D = (46, 90, 56)
SHOE = (35, 38, 46)
SHOE_D = (16, 19, 26)
BLUSH = (243, 172, 176)


def draw_anon_hi(stride=1):
    """96×128 原生侧身像，面向右。头身比约 3.5。"""
    img = Image.new("RGBA", (96, 128), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # —— 背后的吉他包（先画，会被身体压住一半）——
    d.polygon([(26, 36), (38, 30), (48, 96), (36, 102)], fill=(30, 40, 56))
    d.line([(28, 38), (38, 32)], fill=(60, 76, 98))
    d.line([(37, 94), (46, 88)], fill=(60, 76, 98))
    d.polygon([(24, 34), (30, 32), (34, 44), (28, 46)], fill=(20, 27, 38))

    # —— 后发 ——
    d.ellipse([34, 8, 70, 44], fill=HAIR_D)
    d.polygon([(38, 40), (66, 40), (62, 92), (42, 92)], fill=HAIR_D)
    for y0, y1 in ((30, 84), (40, 90), (54, 86)):
        d.line([(46, y0), (43, y1)], fill=HAIR_DD)

    # —— 肩：比头发宽，打破胶囊轮廓 ——
    d.polygon([(38, 58), (48, 60), (68, 60), (72, 66), (70, 78), (40, 78)],
              fill=COAT_D)
    d.line([(40, 60), (70, 60)], fill=COAT_L)

    # —— 头 ——
    d.rounded_rectangle([42, 18, 66, 54], radius=8, fill=SKIN)
    d.polygon([(66, 38), (70, 41), (66, 44)], fill=SKIN)   # 鼻
    d.rectangle([44, 48, 56, 53], fill=SKIN_D)             # 下颌阴影

    # —— 刘海 ——
    d.rectangle([40, 14, 68, 28], fill=HAIR)
    d.ellipse([38, 8, 70, 40], fill=HAIR)
    for x0, x1, tip in ((40, 47, 33), (48, 55, 31), (56, 63, 33), (64, 69, 30)):
        d.polygon([(x0, 28), (x1, 28), ((x0 + x1) // 2, tip)], fill=HAIR)
    d.line([(43, 16), (57, 13)], fill=HAIR_L)
    d.line([(59, 14), (66, 18)], fill=HAIR_L)

    # —— 侧发 ——
    d.rectangle([40, 28, 45, 74], fill=HAIR)
    d.rectangle([40, 56, 43, 74], fill=HAIR_D)
    d.line([(43, 30), (43, 48)], fill=HAIR_L)     # 只在肩以上留高光，别压到脸

    # —— 眉 / 眼 / 腮红 / 嘴 / 虎牙 ——
    d.line([(52, 30), (61, 29)], fill=HAIR_D)

    d.rectangle([51, 33, 60, 42], fill=WHITE)      # 眼白
    d.rectangle([52, 34, 60, 42], fill=EYE)        # 虹膜
    d.rectangle([54, 35, 60, 41], fill=EYE_D)      # 瞳孔区
    d.rectangle([53, 36, 54, 37], fill=WHITE)      # 高光
    d.line([(51, 32), (60, 31)], fill=(118, 66, 80))  # 睫毛
    d.line([(51, 33), (51, 41)], fill=(118, 66, 80))  # 眼外角

    d.rectangle([45, 43, 50, 45], fill=BLUSH)
    d.rectangle([59, 48, 63, 49], fill=(176, 112, 116))
    d.rectangle([62, 49, 64, 51], fill=WHITE)      # 虎牙

    # —— 脖子 ——
    d.rectangle([52, 50, 60, 62], fill=SKIN_D)

    # —— 躯干：外套包住两侧，中间露衬衫 ——
    d.rectangle([44, 62, 66, 92], fill=COAT)
    d.rectangle([54, 64, 62, 90], fill=SHIRT)
    d.line([(54, 64), (54, 90)], fill=SHIRT_D)
    d.line([(62, 64), (62, 90)], fill=SHIRT_D)
    # 领口
    d.polygon([(52, 62), (56, 62), (58, 70), (52, 68)], fill=SHIRT)
    d.polygon([(62, 62), (66, 64), (62, 68)], fill=SHIRT)
    # 翻领
    d.polygon([(44, 62), (52, 62), (58, 72), (48, 84), (44, 74)], fill=COAT)
    d.line([(44, 62), (58, 72)], fill=COAT_L)
    d.line([(58, 72), (48, 84)], fill=COAT_L)
    # 领带
    d.polygon([(57, 66), (61, 66), (62, 78), (59, 86), (55, 78)], fill=TIE)
    d.line([(59, 67), (58, 84)], fill=TIE_D)
    d.line([(56, 70), (62, 71)], fill=TIE_D)
    # 下摆
    d.line([(44, 92), (66, 92)], fill=COAT_L)

    # —— 近侧手臂：比躯干暗一档，形成前后层次 ——
    ax = 50 + stride * 3
    d.rectangle([ax, 70, ax + 9, 90], fill=COAT_D)
    d.line([(ax, 70), (ax, 90)], fill=(120, 126, 138))
    d.rectangle([ax + 1, 90, ax + 9, 98], fill=SKIN)
    d.line([(ax + 1, 92), (ax + 8, 92)], fill=SKIN_D)

    # —— 裙 ——
    d.polygon([(38, 92), (74, 92), (78, 106), (34, 106)], fill=SKIRT)
    for gx in range(40, 76, 8):
        d.line([(gx, 94), (gx - 2, 105)], fill=SKIRT_D)
    d.line([(34, 106), (78, 106)], fill=SKIRT_D)

    # —— 腿 ——
    fx = stride * 4
    d.rectangle([54 + fx, 106, 62 + fx, 122], fill=SOCK)
    d.rectangle([42 - fx, 106, 50 - fx, 122], fill=SOCK)
    d.line([(54 + fx, 106), (54 + fx, 122)], fill=SOCK_D)
    d.line([(42 - fx, 106), (42 - fx, 122)], fill=SOCK_D)
    d.line([(55 + fx, 108), (61 + fx, 108)], fill=SOCK_D)
    d.line([(43 - fx, 108), (49 - fx, 108)], fill=SOCK_D)

    # —— 鞋 ——
    d.rectangle([52 + fx, 122, 68 + fx, 127], fill=SHOE)
    d.rectangle([40 - fx, 122, 56 - fx, 127], fill=SHOE)
    d.line([(52 + fx, 126), (68 + fx, 126)], fill=SHOE_D)
    d.line([(40 - fx, 126), (56 - fx, 126)], fill=SHOE_D)

    return img


def add_outline(sprite, color=(18, 22, 30)):
    """给角色加 1px 冷色描边——在雪地这类高亮背景上，没有描边人物会糊进去。"""
    from PIL import ImageFilter
    alpha = sprite.split()[3]
    grown = alpha.filter(ImageFilter.MaxFilter(3))
    ring = Image.new("RGBA", sprite.size, color + (255,))
    ring.putalpha(grown)
    ring.paste(sprite, (0, 0), sprite)
    return ring


def grade(sprite, ambient=(0.74, 0.80, 0.93), sat=0.62):
    """环境光染色：降饱和 + 冷色偏移，让角色进入场景的光环境。"""
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
            r *= ambient[0]
            g *= ambient[1]
            b *= ambient[2]
            px[x, y] = (int(min(255, r)), int(min(255, g)), int(min(255, b)), a)
    return sprite


def pixelize(img, size, colors):
    small = img.convert("RGB").resize(size, Image.BOX)
    q = small.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)
    return q.convert("RGB")


def compose(scene_path, logical, out_scale, colors, out_path, pos=(0.44, 0.90),
            stride=1):
    base = pixelize(Image.open(scene_path), logical, colors)
    W, H = logical

    sprite = add_outline(grade(draw_anon_hi(stride)))
    sw, sh = sprite.size
    px = int(W * pos[0])
    py = int(H * pos[1]) - sh
    px = max(4, min(px, W - sw - 4))
    py = max(2, min(py, H - sh - 2))

    # 落地阴影
    shadow = Image.new("RGBA", (sw, 14), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([4, 3, sw - 4, 13], fill=(6, 10, 16, 110))
    base.paste(shadow, (px, py + sh - 8), shadow)

    base.paste(sprite, (px, py), sprite)
    out = base.resize((W * out_scale, H * out_scale), Image.NEAREST)
    out.save(out_path)
    return out.size, (px, py)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    s1, _ = compose(args.scene, (960, 540), 2, 40, out / "composite_C_960.png")
    print(f"[ok] composite_C_960.png   {s1}   人物 96×128 原生")

    s2, _ = compose(args.scene, (1280, 720), 2, 48, out / "composite_D_1280.png",
                    pos=(0.42, 0.92))
    print(f"[ok] composite_D_1280.png  {s2}   人物 96×128 原生")


if __name__ == "__main__":
    main()
