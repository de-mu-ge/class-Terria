"""输入事件抽象。

场景只认识 InputEvent，不认识 pygame.event。换引擎时只需改 app 里的映射。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class InputKind(str, enum.Enum):
    ADVANCE = "advance"          # 左键 / 空格 / 回车：推进对话
    CONFIRM = "confirm"          # 菜单确认
    CANCEL = "cancel"            # Esc / 右键
    MENU_UP = "menu_up"
    MENU_DOWN = "menu_down"
    MENU_LEFT = "menu_left"
    MENU_RIGHT = "menu_right"
    MOVE_LEFT = "move_left"        # 按住左右移动（玩法场景用）
    MOVE_RIGHT = "move_right"
    MOVE_STOP = "move_stop"
    POINTER = "pointer"          # 鼠标移动
    CLICK = "click"              # 鼠标左键按下
    FAST_FORWARD_START = "fast_forward_start"
    FAST_FORWARD_END = "fast_forward_end"
    TOGGLE_DEBUG = "toggle_debug"
    QUIT = "quit"


@dataclass(frozen=True)
class InputEvent:
    kind: InputKind
    pos: tuple[int, int] | None = None


FAST_FORWARD_FACTOR = 4.0
