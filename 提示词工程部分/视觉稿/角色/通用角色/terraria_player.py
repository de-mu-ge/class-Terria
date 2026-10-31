#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泰拉瑞亚风格角色 · 48×64 逐像素图（对照参考稿）。

参考稿四条硬特征：
    1. 大刺猬头，轮廓锯齿状
    2. 3/4 侧身，脸朝右，只露一只大白眼睛
    3. 背包在身后（画面左侧），到腰就收，不拖地
    4. 裸手臂 + 肩口一小截袖子；迈步，两腿分开

坐标（48 列）
    背包 x6–12 (y25–42) · 左臂 x13–16 · 上衣 x17–29 · 右臂 x30–33
    头 x10–30 · 脸 x18–30 · 大腿 y39–43 · 小腿 y44–53 · 鞋 y54–58

图例
    . 透明  f 描边  h 发中  H 发暗  i 发亮  s 皮肤  S 肤暗
    w 眼白  k 眼黑  b 上衣  B 衣暗  p 裤  P 裤暗  o 鞋  q 背包  Q 背包暗
"""

import argparse
from pathlib import Path

from PIL import Image

W, H = 48, 64

PALETTE = {
    ".": None,
    "f": (34, 24, 22),
    "h": (152, 66, 46),
    "H": (110, 44, 30),
    "i": (192, 92, 62),
    "s": (242, 150, 104),
    "S": (198, 110, 76),
    "w": (252, 252, 252),
    "k": (40, 30, 30),
    "b": (198, 198, 182),
    "B": (152, 152, 138),
    "p": (210, 192, 148),
    "P": (168, 150, 112),
    "o": (98, 66, 42),
    "q": (112, 134, 180),
    "Q": (80, 98, 138),
}

ART = [
    "................................................",  # 00
    "................................................",  # 01
    "..................ii............................",  # 02
    "...............iiihhiii.........................",  # 03
    ".............iihhhhhhhhhi.......................",  # 04
    "............ihhhhhhhhhhhhhi.....................",  # 05
    "...........ihhhhhhhhhhhhhhhi....................",  # 06
    "..........ihhhhhhhhhhhhhhhhhi...................",  # 07
    "..........hhhhhhhhhhhhhhhhhhh...................",  # 08
    "..........hhhhhhhhhhhhhhhhhhh...................",  # 09
    "..........hhhhhhhhhhhhhhhhhhhh..................",  # 10
    "..........hhhhhhhhhhsssssssshhh.................",  # 11
    "..........hhhhhhhhssssssssssshhh................",  # 12
    "..........hhhhhhhssssssssssssshh................",  # 13
    "..........hhhhhhhssssssssssssshh................",  # 14
    "..........hhhhhhhsssswwwwwwsssshh...............",  # 15
    "..........hhhhhhhsssswwkkwwsssshh...............",  # 16
    "..........hhhhhhhsssswwkkwwsssshh...............",  # 17
    "..........hhhhhhhsssswwwwwwsssshh...............",  # 18
    "..........hhhhhhhsssssssssssssshh...............",  # 19
    "..........hhhhhhhhsssssssssssshhh...............",  # 20
    "...........hhhhhhhhsssssssssshhh................",  # 21
    "............hhhhhhhhhsssssssshh.................",  # 22
    ".............hhhhhhhhhsssssshh..................",  # 23
    "..............hhhhhhhhhfffff....................",  # 24
    "......qqqqqqq..sssssssssssssssss................",  # 25
    ".....qQQqqqqqq.ssssssssssssssssss...............",  # 26
    ".....qQQqqqqqq.ssssbbbbbbbbbbsssss..............",  # 27
    ".....qQQqqqqqq.ssssbbbbbbbbbbbssss..............",  # 28
    ".....qqqqqqqqq.ssssbbbbbbbbbbbssss..............",  # 29
    "......qqqqqqqq.ssssbbbbbbbbbbbssss..............",  # 30
    "......qqqqqqqq.ssssbbbbbbbbBbbssss..............",  # 31
    ".......qqqqqqq.ssssbBBBBBBBBBBsss...............",  # 32
    ".......qqqqqqq.ssssssssssssssssss...............",  # 33
    "........qqqqqq..ssssssssssssssss................",  # 34
    "........qqqqqq...ssssssssssssss.................",  # 35
    "........qqqqqq....wwwwwwwwwwww..................",  # 36
    ".........qqqqq....pppppppppppp..................",  # 37
    ".........qqqqq...ppppppppppppp..................",  # 38
    ".........qqqqq...ppppppppppppp..................",  # 39
    ".........qqqqq...PPppppppppppp..................",  # 40
    "..........qqqq...PPpppppppppp...................",  # 41
    "..........qqqq....PPPPPPPPPPP...................",  # 42
    "..........qqqq....PPP....PPPP...................",  # 43
    "...........qqq....PPP....PPPP...................",  # 44
    "...........qqq....PPP....PPPP...................",  # 45
    ".................PPP....PPPP....................",  # 46
    ".................PPP....PPPP....................",  # 47
    "................PPPPP..PPPPP....................",  # 48
    "................ooooo..ooooo....................",  # 49
    "................ooooo..ooooo....................",  # 50
    "................ooooo..ooooo....................",  # 51
    "................fffff..fffff....................",  # 52
]


def _norm(art):
    rows = [r.ljust(W, ".")[:W] for r in art]
    rows += ["." * W] * (H - len(rows))
    return rows[:H]


def render(art, scale=1):
    rows = _norm(art)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            color = PALETTE.get(ch)
            if color:
                px[x, y] = color + (255,)
    if scale != 1:
        img = img.resize((W * scale, H * scale), Image.NEAREST)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--ruler", action="store_true")
    ap.add_argument("--scale", type=int, default=8)
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    if args.ruler:
        rows = _norm(ART)
        print("     " + "".join(str(i % 10) for i in range(W)))
        for y, r in enumerate(rows):
            print(f"{y:3d}  {r}")

    fig = render(ART, args.scale)
    sheet = Image.new("RGB", (W * args.scale + 40, H * args.scale + 20),
                      (24, 32, 44))
    sheet.paste(fig, (20, 10), fig)
    sheet.save(out / "terraria_player.png")
    print(f"[ok] terraria_player.png ({sheet.width}×{sheet.height})")


if __name__ == "__main__":
    main()
