#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""程序化像素绘制 v2 —— 按《整体风格与UI》规范，用代码验证规范能否落地。

    py1  海岸切片    640×360 逻辑画布 → ×3，场景切片（无角色，交给立绘/ Sprite 层）
    py2  角色精灵表  爱音 48×64 待机 + 行走 4 帧，×2 放大到 96×64 网格审查
    py3  UI 对照稿   3840×1080，左「对话状态」右「探索状态」

绘制顺序遵循游戏管线：远景 → 中景 → 近景 → 暗角，全部整数倍放大。

用法：
    python python_draw.py [--outdir ./]
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 调色板 ----
SKY_TOP = (26, 38, 54)
SKY_MID = (48, 70, 96)
SKY_LOW = (104, 128, 152)
HAZE = (150, 170, 190)
FOG = (169, 188, 207)
SNOW = (211, 222, 233)
MOUNTAIN_FAR = (58, 78, 102)
MOUNTAIN_MID = (40, 54, 74)
MOUNTAIN_NEAR = (27, 38, 53)
FOREST = (21, 30, 42)
SEA_FAR = (48, 70, 94)
SEA_MID = (34, 50, 70)
SEA_NEAR = (24, 34, 48)
WAVE_LIGHT = (120, 145, 170)
FOAM = (206, 220, 232)
FOAM_HI = (236, 243, 248)
SAND = (166, 148, 120)
SAND_D = (132, 116, 92)
SAND_L = (190, 172, 142)
ROCK = (30, 40, 54)
ROCK_L = (72, 96, 122)
ROCK_D = (18, 24, 34)
GRASS = (58, 74, 62)
GRASS_L = (86, 104, 82)
WOOD = (78, 62, 48)
WARM = (242, 166, 90)
GOLD = (201, 162, 39)
TEXT = (237, 239, 242)
TEXT_DIM = (168, 180, 194)

W, H = 640, 360
HORIZON = 198
SHORE = 268

# ---------------------------------------------------------------- 工具 ----


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def to_arr(img):
    return np.array(img).astype(np.int16)


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def ridge(width, base, amps, freqs, phases):
    """用多组正弦叠出自然的山脊线，避免重复三角。"""
    xs = np.arange(width)
    y = np.full(width, float(base))
    for a, f, p in zip(amps, freqs, phases):
        y += a * np.sin(xs * f + p)
    return y


def mountain_profile(width, seed, octaves=5, sharpness=0.65):
    """分形噪声生成山脊：多倍频叠加 + 平滑卷积，出自然峰谷而不是正弦波。"""
    rng = np.random.default_rng(seed)
    acc = np.zeros(width)
    amp, freq = 1.0, 3
    for _ in range(octaves):
        n = rng.normal(0, 1, width)
        ksize = max(5, int(width / freq) | 1)
        k = np.hanning(ksize)
        k /= k.sum()
        acc += np.convolve(n, k, mode="same") * amp
        amp *= 0.55
        freq *= 2
    acc -= acc.min()
    acc /= acc.max()
    return acc ** sharpness


def fill_under(draw, ys, y_bottom, color, x0=0):
    n = len(ys)
    pts = [(x0 + i, int(ys[i])) for i in range(n)]
    pts += [(x0 + n - 1, y_bottom), (x0, y_bottom)]
    draw.polygon(pts, fill=color)


def dither_into(arr, mask, color, seed=0):
    """把某个区域按 50% 棋盘噪声混入颜色，用于雾/霾的过渡。"""
    rng = np.random.default_rng(seed)
    noise = rng.random(mask.shape) > 0.5
    sel = mask & noise
    arr[sel] = color
    return arr


# ---------------------------------------------------------------- 场景 ----


def draw_coast(seed=5):
    img = Image.new("RGB", (W, H), SKY_TOP)
    px = img.load()
    d = ImageDraw.Draw(img)

    # —— 天空：分段平滑过渡（低频区域不用抖动，避免噪点）——
    for y in range(0, HORIZON):
        t = y / (HORIZON - 1)
        if t < 0.55:
            c = lerp(SKY_TOP, SKY_MID, t / 0.55)
        else:
            c = lerp(SKY_MID, SKY_LOW, (t - 0.55) / 0.45)
        d.line([(0, y), (W, y)], fill=c)

    # —— 云：几团堆叠的椭圆，底平顶圆，再压一道顶部受光 ——
    rng = np.random.default_rng(seed)
    cloud_bands = [(116, 9, (52, 70, 94), (68, 88, 114)),
                   (140, 7, (64, 84, 110), (80, 100, 126))]
    for cy, ch, dark, light in cloud_bands:
        x = -40
        while x < W:
            cw = int(rng.integers(80, 200))
            lobes = max(2, cw // 46)
            for i in range(lobes):
                lx = x + int(i * cw / lobes)
                lw = int(cw / lobes * 1.5)
                lh = ch + int(rng.integers(-5, 6))
                d.ellipse([lx, cy, lx + lw, cy + lh * 2], fill=dark)
                # 顶部受光：偏上一层的窄椭圆
                d.ellipse([lx + lw * 0.12, cy + 1, lx + lw * 0.88, cy + lh],
                          fill=light)
            d.rectangle([x + 10, cy + ch, x + cw - 10, cy + ch + 3], fill=dark)
            x += cw + int(rng.integers(20, 90))

    # —— 远山：三层分形山脊 ——
    layers = [
        (MOUNTAIN_FAR, 44, 6, 0.62, (126, 146, 170)),
        (MOUNTAIN_MID, 30, 9, 0.70, None),
        (MOUNTAIN_NEAR, 17, 12, 0.78, None),
    ]
    for li, (color, height, hseed, sharp, snow) in enumerate(layers):
        prof = mountain_profile(W, seed + hseed * 13, sharpness=sharp)
        ys = HORIZON - 4 - height * prof
        fill_under(d, ys, HORIZON, color)
        if snow:
            # 雪线：只在足够高的峰段，贴脊线 2~5px
            for x in range(W):
                if prof[x] < 0.55:
                    continue
                top = int(ys[x])
                d.line([(x, top), (x, top + 2 + int(3 * prof[x]))], fill=snow)

    # —— 海岸针叶林：高低错落的小三角，不是等距梳子 ——
    x = 0
    while x < W:
        hgt = 5 + int(6 * abs(math.sin(x * 0.05) + 0.6 * math.sin(x * 0.17)))
        half = max(2, hgt // 3)
        d.polygon([(x, HORIZON), (x + half, HORIZON - hgt), (x + 2 * half, HORIZON)],
                  fill=FOREST)
        x += half + 1

    # —— 海面 ——
    for y in range(HORIZON, SHORE):
        t = (y - HORIZON) / (SHORE - HORIZON - 1)
        c = lerp(SEA_FAR, SEA_MID, t / 0.5) if t < 0.5 else lerp(SEA_MID, SEA_NEAR, (t - 0.5) / 0.5)
        d.line([(0, y), (W, y)], fill=c)
    # 海平线高光
    d.line([(0, HORIZON), (W, HORIZON)], fill=WAVE_LIGHT)
    d.line([(0, HORIZON + 1), (W, HORIZON + 1)], fill=lerp(WAVE_LIGHT, SEA_FAR, 0.5))

    # 波峰：长而低的横向水纹，越近越亮
    for i, y in enumerate(range(HORIZON + 7, SHORE - 4, 7)):
        w = 0.62 + i * 0.035
        x = int((-i * 53) % 90)
        while x < W:
            ln = int(22 + abs(math.sin(x * 0.07 + i * 1.7)) * 46)
            d.line([(x, y), (x + ln, y)], fill=lerp(WAVE_LIGHT, SEA_FAR, w))
            if ln > 40:
                d.line([(x + 8, y + 2), (x + ln - 10, y + 2)],
                       fill=lerp(FOAM, SEA_MID, 0.45))
            x += ln + int(28 + abs(math.cos(x * 0.05)) * 60)
    # 零星反光
    rng2 = np.random.default_rng(seed + 9)
    for y in range(HORIZON + 4, SHORE - 2, 3):
        for _ in range(3):
            x = int(rng2.integers(0, W))
            px[x, y] = lerp(FOAM_HI, SEA_FAR, 0.25)

    # —— 浪花与海岸线 ——
    ys = ridge(W, SHORE, [5, 3, 1.5], [0.02, 0.06, 0.15], [1.1, 3.7, 0.5])
    fill_under(d, ys, H, SAND)
    for x in range(W):
        top = int(ys[x])
        d.line([(x, top - 1), (x, top + 1)], fill=FOAM_HI)
        d.line([(x, top + 2), (x, top + 5)], fill=FOAM)

    # 湿沙带
    ys_wet = ys + 14 + 5 * np.sin(np.arange(W) * 0.05)
    for x in range(W):
        d.line([(x, int(ys[x]) + 3), (x, int(min(ys_wet[x], H - 1)))], fill=SAND_D)
    # 沙面颗粒
    rng3 = np.random.default_rng(seed + 21)
    for y in range(SHORE - 2, H):
        for x in range(0, W, 2):
            if rng3.random() < 0.10:
                px[x, y] = SAND_L if rng3.random() < 0.5 else SAND_D

    # —— 岩石：圆润多边形 + 左上受光 ——
    def rock(cx, cy, rw, rh):
        pts = []
        for ang in range(0, 360, 20):
            a = math.radians(ang)
            rr = 0.78 + 0.22 * math.sin(ang * 1.7 + cx * 0.1)
            pts.append((cx + math.cos(a) * rw * rr, cy + math.sin(a) * rh * rr))
        d.polygon(pts, fill=ROCK)
        d.line(pts[:len(pts) // 2], fill=ROCK_L)
        d.line(pts[len(pts) // 2:], fill=ROCK_D)

    rock(56, 300, 46, 30)
    rock(120, 314, 26, 16)
    rock(566, 320, 34, 20)

    # —— 岸边杂物 ——
    d.polygon([(170, 300), (208, 296), (210, 302), (172, 306)], fill=WOOD)  # 浮木
    d.line([(172, 300), (208, 296)], fill=(104, 84, 64))
    for (bx, by) in [(250, 322), (312, 316), (420, 330), (500, 322)]:
        d.rectangle([bx, by, bx + 3, by + 2], fill=(96, 88, 74))
        d.point([(bx + 1, by)], fill=(120, 112, 96))

    # —— 草丛：三到五根不等高的叶片 ——
    for gx in (150, 232, 300, 398, 462, 528, 596):
        base = 296 + int(14 * abs(math.sin(gx * 0.09)))
        for k, dx in enumerate((-4, -2, 0, 2, 4)):
            hgt = 6 + (abs(k - 2) * -1 + 3) + (gx % 3)
            d.line([(gx + dx, base), (gx + dx + (1 if dx > 0 else -1 if dx < 0 else 0),
                                      base - hgt)], fill=GRASS)
            px[gx + dx, base - hgt + 1] = GRASS_L

    # —— 暗角 ——
    arr = to_arr(img).astype(float)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / (W * 0.68)) ** 2 + ((yy - H * 0.58) / (H * 0.85)) ** 2)
    vg = np.clip((dist - 0.62) * 1.4, 0, 1) * 0.35
    arr *= (1 - vg[..., None])
    return to_img(arr)


# ---------------------------------------------------------------- 角色 ----
# 24×32 字符画，×2 得到 48×64。符号见 SPRITE_MAP。
SPRITE_IDLE = [
    "........HHHHHHH.........",
    ".......HHHHHHHHH........",
    "......HHHHHHHHHHH.......",
    "......HHHHSSSSSHH.......",
    ".....HHHHSSSSSSSH.......",
    ".....HHHHSSSSSSSH.......",
    ".....HHHHSSSESSESH......",
    ".....HHHHSSSESSESH......",
    ".....HHHHSSSSSSSH.......",
    "......HHHSSSSSSSH.......",
    ".......HHSSSSSSH........",
    "........SSSSSSS.........",
    "......JJJJJJJJJJ........",
    ".....JJJJJJJJJJJJ.......",
    ".....JjJJJJJJJJJj.......",
    ".....JjJJJJJJJJJj.......",
    ".....JjJJJJJJJJJj.......",
    ".....JJJJJJJJJJJJ.......",
    "......KKKKKKKKKK........",
    ".....KKKKKKKKKKKK.......",
    ".....KKKKKKKKKKKK.......",
    "......KKKKKKKKKK........",
    ".......LLLLLLLL.........",
    ".......LLLLLLLL.........",
    ".......LLLLLLLL.........",
    ".......LLLLLLLL.........",
    ".......LLLLLLLL.........",
    "......BBBB..BBBB........",
    "......BBBB..BBBB........",
    "......BBBB..BBBB........",
    "........................",
    "........................",
]

SPRITE_WALK_A = [
    "........HHHHHHH.........",
    ".......HHHHHHHHH........",
    "......HHHHHHHHHHH.......",
    "......HHHHSSSSSHH.......",
    ".....HHHHSSSSSSSH.......",
    ".....HHHHSSSSSSSH.......",
    ".....HHHHSSSESSESH......",
    ".....HHHHSSSESSESH......",
    ".....HHHHSSSSSSSH.......",
    "......HHHSSSSSSSH.......",
    ".......HHSSSSSSH........",
    "........SSSSSSS.........",
    "......JJJJJJJJJJ........",
    ".....JJJJJJJJJJJJ.......",
    "....JjJJJJJJJJJJj.......",
    ".....JjJJJJJJJJJj.......",
    ".....JjJJJJJJJJJj.......",
    ".....JJJJJJJJJJJJ.......",
    "......KKKKKKKKKK........",
    ".....KKKKKKKKKKKK.......",
    ".....KKKKKKKKKKKK.......",
    "......KKKKKKKKKK........",
    "......LLLLLLLLLL........",
    ".....LLLLL..LLLLL.......",
    ".....LLLL....LLLL.......",
    "....LLLL......LLLL......",
    "....LLLL......LLLL......",
    "...BBBBB......BBBBB.....",
    "...BBBBB......BBBBB.....",
    "........................",
    "........................",
    "........................",
]


def _norm(rows, width=24):
    out = []
    for r in rows:
        r = r[:width]
        out.append(r + "." * (width - len(r)))
    return out


def _apply_legs(base, legs):
    """把 base 的第 22 行之后替换成 legs 的对应行，实现腿部动作。"""
    return base[:22] + legs[22:]


SPRITE_MAP = {
    ".": None,
    "H": (198, 146, 122),
    "h": (166, 116, 96),
    "S": (236, 205, 174),
    "E": (58, 66, 84),
    "J": (234, 231, 224),
    "j": (188, 188, 184),
    "K": (43, 56, 78),
    "L": (211, 222, 233),
    "B": (30, 40, 54),
}


def draw_sprite_frame(canvas, ox, oy, rows, scale=2):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = SPRITE_MAP.get(ch)
            if not color:
                continue
            canvas.paste(color, (ox + x * scale, oy + y * scale,
                                 ox + x * scale + scale - 1, oy + y * scale + scale - 1))


def sprite_sheet():
    cell_w, cell_h, scale, pad = 24, 32, 6, 28
    label_h = 46
    frames = [
        ("待机", _norm(SPRITE_IDLE)),
        ("迈步 A", _norm(SPRITE_WALK_A)),
        ("并腿", _norm(_apply_legs(_norm(SPRITE_IDLE), _norm(SPRITE_IDLE)))),
        ("迈步 B", _norm(SPRITE_WALK_A[::-1][::-1])),
        ("并腿", _norm(SPRITE_IDLE)),
    ]
    # 迈步 B：只镜像腿部，身体保持朝向
    walk_a = _norm(SPRITE_WALK_A)
    b_rows = walk_a[:22] + [r[::-1] for r in walk_a[22:]]
    frames[3] = ("迈步 B", b_rows)

    cols = len(frames)
    w = pad + cols * (cell_w * scale + pad)
    h = pad + label_h + cell_h * scale + pad + 30
    sheet = Image.new("RGB", (w, h), (16, 22, 30))
    d = ImageDraw.Draw(sheet)

    # 16px 网格参考
    for gx in range(0, w, 16):
        d.line([(gx, 0), (gx, h)], fill=(24, 33, 44))
    for gy in range(0, h, 16):
        d.line([(0, gy), (w, gy)], fill=(24, 33, 44))

    ground = pad + label_h + cell_h * scale
    d.rectangle([0, ground, w, h], fill=(22, 30, 40))
    d.line([(0, ground + 2), (w, ground + 2)], fill=(78, 100, 126))

    font = load_font(22)
    for i, (label, rows) in enumerate(frames):
        cx = pad + i * (cell_w * scale + pad)
        d.rectangle([cx - 2, pad + label_h - 2, cx + cell_w * scale + 1,
                     pad + label_h + cell_h * scale + 1], outline=(54, 70, 92))
        draw_sprite_frame(sheet, cx, pad + label_h, rows, scale)
        if font:
            d.text((cx + 2, 12), label, font=font, fill=(160, 176, 194))
            d.text((cx + 2, h - 26), "48×64", font=load_font(16), fill=(110, 126, 146))
    return sheet


# ---------------------------------------------------------------- 字体 ----
_FONT_CACHE = {}


def load_font(size):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    for path in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"):
        try:
            f = ImageFont.truetype(path, size)
            _FONT_CACHE[size] = f
            return f
        except OSError:
            continue
    _FONT_CACHE[size] = None
    return None


def text(d, xy, s, size, color):
    f = load_font(size)
    if f:
        d.text(xy, s, font=f, fill=color)


# ---------------------------------------------------------------- UI ----
def panel_dialogue(size):
    """对话状态：Galgame 对话框 + 名字条。"""
    S = 3
    img = draw_coast(seed=5).resize((W * S, H * S), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")

    dx0, dy0, dx1, dy1 = 24 * S, 262 * S, 616 * S, 344 * S
    d.rectangle([dx0, dy0, dx1, dy1], fill=(11, 18, 25, 216))
    d.rectangle([dx0, dy0, dx1, dy1], outline=GOLD, width=3)
    d.rectangle([dx0 + 3, dy0 + 3, dx1 - 3, dy1 - 3], outline=(0, 0, 0, 150), width=1)

    nx0, ny0, nx1, ny1 = 24 * S, 234 * S, 186 * S, 262 * S
    d.rectangle([nx0, ny0, nx1, ny1], fill=(11, 18, 25, 240))
    d.rectangle([nx0, ny0, nx1, ny1], outline=GOLD, width=3)
    text(d, (nx0 + 14, ny0 + 9), "千早爱音", 30, TEXT)

    text(d, (dx0 + 40, dy0 + 26), "……好冷。", 34, TEXT)
    text(d, (dx0 + 40, dy0 + 84), "这里……是哪里？", 34, TEXT_DIM)
    text(d, (dx1 - 58, dy1 - 48), "▼", 30, GOLD)
    return img


def panel_explore(size):
    """探索状态：HP / 体温 / 快捷栏 / 时间天气。"""
    S = 3
    img = draw_coast(seed=5).resize((W * S, H * S), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")

    def bar(x, y, label, ratio, color):
        text(d, (x, y - 34), label, 24, TEXT_DIM)
        d.rectangle([x, y, x + 288, y + 18], fill=(14, 21, 30, 205))
        d.rectangle([x, y, x + int(288 * ratio), y + 18], fill=color)
        d.rectangle([x, y, x + 288, y + 18], outline=(96, 116, 140, 230), width=2)

    bar(72, 116, "HP", 0.78, (194, 69, 61))
    bar(72, 190, "体温", 0.34, WARM)

    text(d, (W * S - 320, 74), "傍晚 · 阴", 26, TEXT_DIM)

    slots, size, gap = 8, 96, 14
    total = slots * size + (slots - 1) * gap
    sx = (W * S - total) // 2
    sy = H * S - size - 42
    for i in range(slots):
        x = sx + i * (size + gap)
        d.rectangle([x, sy, x + size, sy + size], fill=(12, 19, 27, 210))
        d.rectangle([x, sy, x + size, sy + size],
                    outline=GOLD if i == 0 else (84, 102, 124, 230), width=2)
    d.rectangle([sx - 4, sy - 10, sx + size + 4, sy + size + 2], outline=GOLD, width=2)
    return img


def ui_mock():
    S = 3
    left = panel_dialogue(S)
    right = panel_explore(S)
    canvas = Image.new("RGB", (W * S * 2 + 24, H * S + 92), (12, 17, 24))
    d = ImageDraw.Draw(canvas)
    canvas.paste(left, (8, 60))
    canvas.paste(right, (W * S + 16, 60))
    text(d, (8, 14), "对话状态 · Galgame 对话框", 30, TEXT)
    text(d, (W * S + 16, 14), "探索状态 · HUD + 快捷栏", 30, TEXT)
    d.line([(W * S + 4, 40), (W * S + 4, canvas.height - 12)], fill=(44, 58, 76), width=2)
    return canvas


# ---------------------------------------------------------------- 入口 ----


def main():
    ap = argparse.ArgumentParser(description="程序化像素绘制 v2")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    coast = draw_coast(seed=5)
    coast.resize((W * 3, H * 3), Image.NEAREST).save(out / "py1_coast_slice.png")
    print("[ok] py1_coast_slice.png")

    sheet = sprite_sheet()
    sheet.save(out / "py2_sprite_sheet.png")
    print(f"[ok] py2_sprite_sheet.png ({sheet.width}×{sheet.height})")

    ui_mock().save(out / "py3_ui_mock.png")
    print("[ok] py3_ui_mock.png (3840×1172)")


if __name__ == "__main__":
    main()
