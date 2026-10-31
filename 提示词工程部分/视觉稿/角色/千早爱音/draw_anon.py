#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""千早爱音 · 48×64 像素立绘（程序化绘制）。

严格按《角色设定》规范：
    发色粉 / 瞳色灰 / 羽丘高一绿色学员色 / 白衬衫 + 浅灰西装 + 绿色领带格子裙及膝袜
先按 1× 像素逐点绘制，再整数倍放大到 8×，保证边缘绝对干净。

用法：
    python draw_anon.py [--outdir ./]
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 调色板 ----
HAIR = (240, 163, 184)
HAIR_D = (201, 124, 144)
HAIR_L = (255, 198, 212)
SKIN = (247, 223, 201)
SKIN_D = (227, 192, 166)
EYE = (140, 147, 160)
EYE_D = (95, 102, 115)
EYE_L = (220, 225, 232)
SHIRT = (255, 255, 255)
SHIRT_D = (221, 224, 230)
COAT = (201, 205, 212)
COAT_D = (164, 169, 179)
COAT_L = (237, 240, 244)
TIE = (78, 140, 90)
TIE_D = (51, 96, 61)
SKIRT = (62, 122, 78)
SKIRT_D = (42, 86, 55)
SOCK = (78, 140, 90)
SOCK_D = (51, 96, 61)
SHOE = (35, 38, 46)
SHOE_D = (20, 23, 32)
BLUSH = (243, 175, 178)
BG = (22, 30, 41)
GOLD = (201, 162, 39)
TXT = (237, 239, 242)
TXT_DIM = (160, 174, 190)

W, H = 48, 64


def draw_anon():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # —— 后发：头顶圆润，垂到腰际 ——
    d.ellipse([11, 3, 36, 30], fill=HAIR_D)
    d.polygon([(13, 24), (34, 24), (32, 48), (15, 48)], fill=HAIR_D)

    # —— 头 ——
    d.rounded_rectangle([15, 6, 32, 27], radius=4, fill=SKIN)

    # —— 刘海：四缕不等长的碎发，露出额头 ——
    d.rectangle([14, 4, 33, 11], fill=HAIR)
    d.ellipse([13, 2, 34, 15], fill=HAIR)
    for x0, x1, tip in ((14, 17, 17), (19, 22, 16), (24, 27, 17), (29, 32, 15)):
        d.polygon([(x0, 10), (x1, 10), ((x0 + x1) // 2, tip)], fill=HAIR)
    d.line([(17, 7), (27, 6)], fill=HAIR_L)          # 发顶高光
    d.line([(28, 6), (31, 8)], fill=HAIR_L)

    # —— 侧发：两缕贴脸垂下 ——
    d.rectangle([13, 12, 14, 38], fill=HAIR)
    d.rectangle([33, 12, 34, 38], fill=HAIR)
    d.rectangle([13, 30, 14, 38], fill=HAIR_D)
    d.rectangle([33, 30, 34, 38], fill=HAIR_D)

    # —— 眉 ——
    d.line([(18, 14), (20, 14)], fill=HAIR_D)
    d.line([(27, 14), (29, 14)], fill=HAIR_D)

    # —— 眼：4×4，右侧虹膜，一点高光 ——
    for ex in (17, 26):
        d.rectangle([ex, 16, ex + 3, 19], fill=EYE_L)
        d.rectangle([ex + 1, 16, ex + 3, 19], fill=EYE)
        d.rectangle([ex + 2, 16, ex + 3, 17], fill=EYE_D)
        d.point([(ex + 1, 17)], fill=(255, 255, 255))
        d.line([(ex, 15), (ex + 3, 15)], fill=HAIR_D)   # 睫毛

    # —— 腮红 / 嘴 / 虎牙 ——
    d.rectangle([15, 20, 16, 20], fill=BLUSH)
    d.rectangle([31, 20, 32, 20], fill=BLUSH)
    d.rectangle([23, 22, 25, 22], fill=(178, 116, 118))
    d.point([(25, 23)], fill=(255, 255, 255))

    # —— 脖子 ——
    d.rectangle([21, 26, 26, 30], fill=SKIN_D)

    # —— 衬衫与领口 ——
    d.rectangle([16, 30, 31, 43], fill=SHIRT)
    d.polygon([(19, 30), (24, 35), (21, 40), (17, 33)], fill=SHIRT)
    d.polygon([(29, 30), (24, 35), (27, 40), (31, 33)], fill=SHIRT)
    d.line([(17, 33), (19, 30)], fill=SHIRT_D)
    d.line([(31, 33), (29, 30)], fill=SHIRT_D)

    # —— 领带（一年级绿）——
    d.polygon([(23, 31), (25, 31), (26, 36), (24, 40), (22, 36)], fill=TIE)
    d.line([(24, 32), (24, 37)], fill=TIE_D)

    # —— 西装外套 ——
    d.polygon([(16, 31), (19, 31), (18, 44), (12, 44), (12, 35)], fill=COAT)
    d.polygon([(31, 31), (29, 31), (29, 44), (35, 44), (35, 35)], fill=COAT)
    d.rectangle([16, 42, 31, 44], fill=COAT)
    d.line([(12, 35), (16, 31)], fill=COAT_L)
    d.line([(35, 35), (31, 31)], fill=COAT_L)
    d.line([(12, 44), (35, 44)], fill=COAT_L)
    d.rectangle([12, 40, 13, 44], fill=COAT_D)
    d.rectangle([34, 40, 35, 44], fill=COAT_D)

    # —— 手 ——
    d.rectangle([12, 44, 14, 47], fill=SKIN)
    d.rectangle([33, 44, 35, 47], fill=SKIN)

    # —— 格子百褶裙 ——
    d.polygon([(14, 47), (33, 47), (36, 53), (11, 53)], fill=SKIRT)
    for gx in range(13, 36, 4):
        d.line([(gx, 48), (gx - 1, 52)], fill=SKIRT_D)
    d.line([(11, 53), (36, 53)], fill=SKIRT_D)

    # —— 及膝袜 ——
    d.rectangle([16, 53, 21, 60], fill=SOCK)
    d.rectangle([26, 53, 31, 60], fill=SOCK)
    d.line([(16, 53), (16, 60)], fill=SOCK_D)
    d.line([(31, 53), (31, 60)], fill=SOCK_D)

    # —— 鞋 ——
    d.rectangle([15, 60, 22, 63], fill=SHOE)
    d.rectangle([25, 60, 32, 63], fill=SHOE)
    d.line([(15, 63), (22, 63)], fill=SHOE_D)
    d.line([(25, 63), (32, 63)], fill=SHOE_D)

    return img


# ---------------------------------------------------------------- 字体 ----
_FONTS = {}


def font(size):
    if size not in _FONTS:
        for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
            try:
                _FONTS[size] = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
        else:
            _FONTS[size] = None
    return _FONTS[size]


def text(d, xy, s, size, color):
    f = font(size)
    if f:
        d.text(xy, s, font=f, fill=color)


def build_card(scale=8):
    fig = draw_anon()
    fw, fh = W * scale, H * scale

    card_w, card_h = 1500, 820
    card = Image.new("RGB", (card_w, card_h), BG)
    d = ImageDraw.Draw(card)

    # 立绘底框 + 16px 网格
    ox, oy = 60, 90
    d.rectangle([ox - 8, oy - 8, ox + fw + 8, oy + fh + 8], fill=(16, 22, 31))
    for gx in range(ox, ox + fw + 1, 16 * scale):
        d.line([(gx, oy), (gx, oy + fh)], fill=(26, 35, 47))
    for gy in range(oy, oy + fh + 1, 16 * scale):
        d.line([(ox, gy), (ox + fw, gy)], fill=(26, 35, 47))
    d.line([(ox - 8, oy + fh), (ox + fw + 8, oy + fh)], fill=GOLD, width=2)

    fig = fig.resize((fw, fh), Image.NEAREST)
    card.paste(fig, (ox, oy), fig)

    # 标题
    text(d, (60, 26), "千早爱音 · Chihaya Anon", 34, TXT)
    text(d, (ox, oy + fh + 26), "48 × 64 px · 1× 像素 · 8× 显示 · 色数 15", 20, TXT_DIM)

    # 右侧信息
    px = ox + fw + 70
    text(d, (px, 96), "官方设定", 26, GOLD)
    rows = [
        ("发色", "粉发 · 长直 · 齐刘海"),
        ("瞳色", "灰瞳"),
        ("身高", "160 cm"),
        ("生日", "9 月 8 日"),
        ("代表色", "#FF8899"),
        ("学校", "羽丘女子学园 高一 A 组"),
        ("制服", "白衬衫 / 浅灰西装 / 绿领带"),
        ("", "绿格子百褶裙 / 绿及膝袜"),
        ("特征", "虎牙 · 常背吉他包"),
    ]
    y = 146
    for k, v in rows:
        if k:
            text(d, (px, y), k, 21, TXT_DIM)
        text(d, (px + 96, y), v, 21, TXT)
        y += 40

    # 色板
    text(d, (px, y + 24), "Sprite 配色", 26, GOLD)
    chips = [
        ("头发", HAIR), ("头发暗", HAIR_D), ("皮肤", SKIN),
        ("眼睛", EYE), ("衬衫", SHIRT), ("外套", COAT),
        ("领带", TIE), ("裙子", SKIRT), ("袜子", SOCK),
        ("鞋", SHOE),
    ]
    cy = y + 74
    for i, (name, col) in enumerate(chips):
        cxp = px + (i % 5) * 108
        cyp = cy + (i // 5) * 96
        d.rectangle([cxp, cyp, cxp + 56, cyp + 56], fill=col,
                    outline=(60, 70, 84))
        text(d, (cxp, cyp + 62), name, 16, TXT_DIM)

    return card


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    fig = draw_anon()
    fig.resize((W * 8, H * 8), Image.NEAREST).save(out / "anon_py_sprite.png")
    print("[ok] anon_py_sprite.png  (48×64 → 384×512)")

    build_card().save(out / "anon_py_card.png")
    print("[ok] anon_py_card.png    (1500×820)")


if __name__ == "__main__":
    main()
