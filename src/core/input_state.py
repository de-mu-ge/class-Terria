"""鼠标 / 键盘的持续状态。

InputEvent 负责「按下/松开」这种一次性事件；
需要「按住」语义的玩法（挖掘、放置、拖动）从这里每帧读状态。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MouseState:
    pos: tuple[int, int] | None = None
    left: bool = False
    right: bool = False

    def move(self, pos: tuple[int, int]) -> None:
        self.pos = pos

    def set_button(self, button: int, pressed: bool) -> None:
        if button == 1:
            self.left = pressed
        elif button == 3:
            self.right = pressed
