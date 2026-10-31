"""小特效（数据里以 {"cmd":"effect","id":...} 触发）。

当前只有 Scene 04 的「一条鱼跃出水面」。
"""

from __future__ import annotations

import math

from ..core.timeline import clamp01
from ..core.types import Color, Rect
from ..render.renderer import Renderer


class FishJump:
    duration: float

    def __init__(self, x0: float, x1: float, y0: float, height: float, duration: float,
                 color: Color) -> None:
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.height = height
        self.duration = max(0.1, duration)
        self.color = color
        self.elapsed = 0.0
        self.done = False

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.done = True

    def draw(self, renderer: Renderer, offset: tuple[float, float] = (0.0, 0.0)) -> None:
        t = clamp01(self.elapsed / self.duration)
        if t <= 0.0 or t >= 1.0:
            return
        x = self.x0 + (self.x1 - self.x0) * t
        y = self.y0 - self.height * math.sin(math.pi * t)
        x += offset[0]
        y += offset[1]
        # 简单鱼形：身体（椭圆状矩形）+ 尾巴三角
        length = 14
        thick = 5
        renderer.draw_rect(Rect(x - length / 2, y - thick / 2, length, thick), self.color, alpha=235)
        tail_x = x - length / 2
        renderer.draw_polygon([(tail_x, y), (tail_x - 6, y - 5), (tail_x - 6, y + 5)],
                              self.color, alpha=235)
        # 水花：落点附近两粒白点
        renderer.draw_rect(Rect(self.x1 + offset[0] - 4, self.y0 + offset[1] - 2, 3, 3),
                           self.color, alpha=170)
        renderer.draw_rect(Rect(self.x1 + offset[0] + 4, self.y0 + offset[1] + 2, 2, 2),
                           self.color, alpha=140)
