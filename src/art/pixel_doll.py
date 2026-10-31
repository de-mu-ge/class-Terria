"""程序化像素角色（未知世界阶段占位）。

没有爱音的正式 Sprite，也不能让 Scene 07 崩，因此用代码按 16px 网格画一组占位帧：
    lying / lying_breathe / sitting / idle / walk_1 / walk_2
配色取角色设定里的千早爱音基准色（粉发 / 灰瞳 / 绿色一年级配色 / 深色吉他包）。
全部是纯像素矩形，无抗锯齿，符合「硬像素」规范；正式 Sprite 到位后替换这里即可。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PixelPalette:
    hair: str = "#F0A3B8"
    hair_dark: str = "#C97C90"
    hair_light: str = "#FFC6D4"
    skin: str = "#F7DFC9"
    skin_dark: str = "#E3C0A6"
    eye: str = "#8C93A0"
    shirt: str = "#FFFFFF"
    blazer: str = "#C9CDD4"
    skirt: str = "#3E7A4E"
    skirt_dark: str = "#2A5637"
    sock: str = "#4E8C5A"
    shoe: str = "#23262E"
    bag: str = "#2D3442"
    bag_light: str = "#3E4757"


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.data = bytearray(width * height * 4)

    def px(self, x: int, y: int, color: str) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        hex_value = color.lstrip("#")
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
        index = (y * self.width + x) * 4
        self.data[index] = r
        self.data[index + 1] = g
        self.data[index + 2] = b
        self.data[index + 3] = 255

    def rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, color)

    def to_bytes(self) -> bytes:
        return bytes(self.data)


class PixelFigure:
    """千早爱音的程序化占位帧。"""

    def __init__(self, palette: PixelPalette | None = None) -> None:
        self.p = palette or PixelPalette()

    # --- 对外 ---------------------------------------------------------
    def frame_size(self, pose: str) -> tuple[int, int]:
        if pose in ("lying", "lying_breathe"):
            return (56, 24)
        if pose == "sitting":
            return (32, 44)
        return (32, 64)

    def build(self, pose: str) -> tuple[int, int, bytes]:
        if pose in ("lying", "lying_breathe"):
            canvas = self._lying(pose == "lying_breathe")
        elif pose == "sitting":
            canvas = self._sitting()
        elif pose == "walk_1":
            canvas = self._standing(leg_shift=-2, body_drop=1)
        elif pose == "walk_2":
            canvas = self._standing(leg_shift=2, body_drop=0)
        else:
            canvas = self._standing(leg_shift=0, body_drop=0)
        return canvas.width, canvas.height, canvas.to_bytes()

    # --- 站姿 ---------------------------------------------------------
    def _standing(self, leg_shift: int, body_drop: int) -> _Canvas:
        p = self.p
        c = _Canvas(32, 64)
        drop = body_drop
        # 吉他包（身后，稍偏右）
        c.rect(24, 16 + drop, 7, 36, p.bag)
        c.rect(25, 18 + drop, 5, 32, p.bag_light)
        c.rect(24, 30 + drop, 7, 3, p.shoe)
        # 长发（垂到腰）
        c.rect(6, 8 + drop, 4, 26, p.hair_dark)
        c.rect(22, 8 + drop, 4, 26, p.hair_dark)
        # 头
        c.rect(8, 4 + drop, 16, 15, p.hair)
        c.rect(8, 2 + drop, 16, 3, p.hair_light)
        c.rect(10, 10 + drop, 12, 9, p.skin)
        c.rect(10, 10 + drop, 12, 2, p.skin_dark)
        # 眼睛
        c.rect(12, 13 + drop, 2, 2, p.eye)
        c.rect(19, 13 + drop, 2, 2, p.eye)
        # 身体
        c.rect(14, 19 + drop, 4, 3, p.skin_dark)          # 脖子
        c.rect(10, 22 + drop, 12, 12, p.shirt)
        c.rect(9, 22 + drop, 2, 12, p.blazer)
        c.rect(21, 22 + drop, 2, 12, p.blazer)
        c.rect(15, 22 + drop, 2, 8, p.skirt_dark)         # 领带
        # 裙子
        c.rect(9, 34 + drop, 14, 6, p.skirt)
        c.rect(9, 38 + drop, 14, 2, p.skirt_dark)
        # 腿
        left_x = 12 + leg_shift
        right_x = 18 - leg_shift
        c.rect(left_x, 40 + drop, 3, 12, p.skin)
        c.rect(right_x, 40 + drop, 3, 12, p.skin)
        # 袜
        c.rect(left_x, 48 + drop, 3, 6, p.sock)
        c.rect(right_x, 48 + drop, 3, 6, p.sock)
        # 鞋
        c.rect(left_x - 1, 54 + drop, 5, 4, p.shoe)
        c.rect(right_x - 1, 54 + drop, 5, 4, p.shoe)
        return c

    # --- 坐姿 ---------------------------------------------------------
    def _sitting(self) -> _Canvas:
        p = self.p
        c = _Canvas(32, 44)
        # 吉他包斜靠
        c.rect(23, 14, 7, 26, p.bag)
        c.rect(24, 16, 5, 22, p.bag_light)
        # 长发
        c.rect(6, 6, 4, 20, p.hair_dark)
        c.rect(22, 6, 4, 20, p.hair_dark)
        # 头
        c.rect(8, 2, 16, 15, p.hair)
        c.rect(8, 0, 16, 3, p.hair_light)
        c.rect(10, 8, 12, 8, p.skin)
        c.rect(12, 11, 2, 2, p.eye)
        c.rect(19, 11, 2, 2, p.eye)
        # 身体
        c.rect(14, 17, 4, 3, p.skin_dark)
        c.rect(10, 20, 12, 10, p.shirt)
        c.rect(9, 20, 2, 10, p.blazer)
        c.rect(21, 20, 2, 10, p.blazer)
        # 曲起的腿
        c.rect(8, 30, 16, 6, p.skirt)
        c.rect(8, 34, 16, 2, p.skirt_dark)
        c.rect(10, 36, 12, 4, p.skin)
        c.rect(10, 40, 12, 3, p.shoe)
        return c

    # --- 倒地 ---------------------------------------------------------
    def _lying(self, breathe: bool) -> _Canvas:
        p = self.p
        c = _Canvas(56, 24)
        bob = 1 if breathe else 0
        # 长发铺在沙上
        c.rect(2, 8 + bob, 16, 6, p.hair_dark)
        # 头（左侧）
        c.rect(4, 6 + bob, 14, 12, p.hair)
        c.rect(4, 4 + bob, 14, 3, p.hair_light)
        c.rect(8, 10 + bob, 9, 7, p.skin)
        c.rect(10, 12 + bob, 2, 2, p.eye)
        c.rect(14, 12 + bob, 2, 2, p.eye)
        # 身体（向右）
        c.rect(17, 9 + bob, 16, 10, p.shirt)
        c.rect(17, 8 + bob, 16, 2, p.blazer)
        c.rect(18, 15 + bob, 15, 5, p.skirt)
        # 腿
        c.rect(33, 11 + bob, 12, 4, p.skin)
        c.rect(44, 11 + bob, 6, 4, p.sock)
        c.rect(49, 10 + bob, 5, 6, p.shoe)
        # 手臂
        c.rect(17, 13 + bob, 8, 3, p.skin)
        # 吉他包放在旁边
        c.rect(26, 16 + bob, 20, 5, p.bag)
        c.rect(27, 17 + bob, 18, 3, p.bag_light)
        return c
