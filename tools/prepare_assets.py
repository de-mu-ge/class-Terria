"""把视觉稿里的参考图转成游戏可直接读取的背景资产。

- 现实世界段落：保留原始比例（镜头可以上下/左右取景），宽度上限 1920，LANCZOS 降采样。
- 未知世界段落：严格降到 960×540，用 NEAREST 保留硬像素，不引入模糊。
- 只读 视觉稿/，只写 assets/backgrounds/prologue/，可重复执行。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "提示词工程部分" / "视觉稿"
DST = ROOT / "assets" / "backgrounds" / "prologue"

# (源文件, 输出名, 模式, 说明)
PLAN: list[tuple[str, str, str, str]] = [
    ("序章_v1/02_scene01_plaza.jpg", "s01_plaza.png", "smooth", "Scene 01/02 樱花广场"),
    ("序章_v1/03_scene03_port.jpg", "s03_port.png", "smooth", "Scene 03 港口与客轮"),
    ("序章_v1/04_scene04_deck.jpg", "s04_deck.png", "smooth", "Scene 04 客轮甲板"),
    ("序章_v1/05_scene05_storm.jpg", "s05_storm.png", "smooth", "Scene 05/06 风暴海面"),
    ("序章_v1/06_scene06_island.jpg", "s06_island.png", "smooth", "Scene 06 雾中岛屿"),
    ("序章_v2/python/py1_coast_slice.png", "s07_coast.png", "pixel", "Scene 07 像素海岸"),
]

LOGICAL = (960, 540)
PIXEL_NATIVE = (LOGICAL[0] * 2, LOGICAL[1] * 2)  # 像素段用 2 倍图，运行时按 2.0 镜头 1:1 取像
MAX_WIDTH = 1920


def prepare() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    produced = 0
    for relative, name, mode, note in PLAN:
        source = SRC / relative
        if not source.is_file():
            print(f"[跳过] 找不到源图：{relative}", file=sys.stderr)
            continue
        with Image.open(source) as image:
            image = image.convert("RGB")
            if mode == "pixel":
                if image.size != PIXEL_NATIVE:
                    image = image.resize(PIXEL_NATIVE, Image.NEAREST)
            else:
                if image.width > MAX_WIDTH:
                    height = round(image.height * MAX_WIDTH / image.width)
                    image = image.resize((MAX_WIDTH, height), Image.LANCZOS)
            target = DST / name
            image.save(target, format="PNG", optimize=True)
            print(f"[写出] {target.relative_to(ROOT)}  {image.width}x{image.height}  {note}")
            produced += 1
    if build_cabin():
        produced += 1
    return produced


def build_cabin() -> bool:
    """生成客舱内景占位背景（视觉稿里没有船舱内部，必须有一张不崩的占位）。

    构图：暗色舱壁 + 舷窗（窗外海面）+ 天花板灯带 + 座椅，纯色块，风格与像素段一致的低饱和冷调。
    """
    from PIL import ImageDraw

    width, height = PIXEL_NATIVE
    image = Image.new("RGB", (width, height), "#161E29")
    draw = ImageDraw.Draw(image)
    # 舱壁竖向渐变
    top = (27, 36, 51)
    bottom = (16, 24, 34)
    for y in range(int(height * 0.72)):
        t = y / max(1, int(height * 0.72))
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    # 地板与踢脚线
    draw.rectangle([0, int(height * 0.72), width, height], fill="#111923")
    draw.line([(0, int(height * 0.72)), (width, int(height * 0.72))], fill="#26364A", width=6)
    # 天花板灯带（熄灭状态：只剩暗色）
    draw.rectangle([int(width * 0.28), int(height * 0.1), int(width * 0.72), int(height * 0.13)],
                   fill="#2A3546")
    # 三扇舷窗
    for cx in (int(width * 0.22), int(width * 0.5), int(width * 0.78)):
        radius = int(width * 0.058)
        cy = int(height * 0.38)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill="#26364A")
        inner = int(radius * 0.82)
        draw.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill="#101822")
        draw.rectangle([cx - inner, cy + inner // 3, cx + inner, cy + inner], fill="#1B2433")
        for i in range(4):
            wy = cy + inner // 3 + i * 8
            draw.line([(cx - inner + 6, wy), (cx + inner - 6, wy)], fill="#26364A", width=2)
    # 座椅
    for x0 in (int(width * 0.06), int(width * 0.79)):
        draw.rectangle([x0, int(height * 0.58), x0 + int(width * 0.14), int(height * 0.66)],
                       fill="#23262E")
        draw.rectangle([x0 + 8, int(height * 0.66), x0 + int(width * 0.14) - 8, int(height * 0.72)],
                       fill="#1A1F27")
    target = DST / "s05_cabin.png"
    image.save(target, format="PNG", optimize=True)
    print(f"[写出] {target.relative_to(ROOT)}  {width}x{height}  Scene 05/06 客舱内景（程序化占位）")
    return True


if __name__ == "__main__":
    count = prepare()
    print(f"完成，共 {count} 张背景资产")
