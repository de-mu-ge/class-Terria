"""输入持续状态：鼠标位置/按键按下集合。

InputEvent 表达「按下/松开」的一次性事件；
玩法需要「按住」语义（游泳、下蹲、持续采集）时从这里每帧读。
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class KeyboardState:
    held: set[str] = field(default_factory=set)

    def press(self, name: str) -> None:
        self.held.add(name)

    def release(self, name: str) -> None:
        self.held.discard(name)

    def down(self, name: str) -> bool:
        return name in self.held

    def axis_x(self) -> int:
        left = self.down("left")
        right = self.down("right")
        if left == right:
            return 0
        return 1 if right else -1
