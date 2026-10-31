"""场景基类。

每个 Scene 实现 enter / update / handle_event / draw / exit，
相互之间不直接引用，只能通过 SceneStack 切换（见 scene_stack.py）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .events import InputEvent

if TYPE_CHECKING:  # pragma: no cover
    from .context import SceneContext


class Scene(ABC):
    scene_id: str = "scene"

    def __init__(self, ctx: "SceneContext") -> None:
        self.ctx = ctx

    # --- 生命周期 -----------------------------------------------------
    def enter(self) -> None:
        """进入场景：准备数据、播放入场演出。"""

    def exit(self) -> None:
        """离开场景：释放场景内的临时状态。"""

    # --- 每帧 ---------------------------------------------------------
    def update(self, dt: float) -> None:
        """固定步长更新。"""

    def handle_event(self, event: InputEvent) -> None:
        """处理单条输入事件。"""

    @abstractmethod
    def draw(self) -> None:
        """绘制当前帧。"""
