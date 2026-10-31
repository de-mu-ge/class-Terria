"""场景栈。

规则：
1. 场景之间不互相持有引用，切换一律通过本栈（push / pop / replace / set）。
2. 切换请求先入队，在本帧 update 结束后统一结算，避免场景在自身 update 中途被销毁。
3. 入队的是“工厂函数”，每次切换都新建实例 —— 保证退出后重进状态干净。
"""

from __future__ import annotations

import logging
from typing import Callable, List, Tuple

from .context import SceneContext
from .scene import Scene

log = logging.getLogger(__name__)

SceneFactory = Callable[[], Scene]


class SceneStack:
    def __init__(self, ctx_factory: Callable[[], SceneContext]) -> None:
        self._ctx_factory = ctx_factory
        self._stack: List[Scene] = []
        self._pending: List[Tuple[str, SceneFactory | None]] = []

    # --- 查询 ---------------------------------------------------------
    @property
    def top(self) -> Scene | None:
        return self._stack[-1] if self._stack else None

    @property
    def depth(self) -> int:
        return len(self._stack)

    def is_empty(self) -> bool:
        return not self._stack

    def scene_ids(self) -> List[str]:
        return [s.scene_id for s in self._stack]

    # --- 请求（不立即生效） -------------------------------------------
    def push(self, factory: SceneFactory) -> None:
        self._pending.append(("push", factory))

    def pop(self) -> None:
        self._pending.append(("pop", None))

    def replace(self, factory: SceneFactory) -> None:
        self._pending.append(("replace", factory))

    def set(self, factory: SceneFactory) -> None:
        self._pending.append(("set", factory))

    # --- 结算 ---------------------------------------------------------
    def flush(self) -> None:
        while self._pending:
            op, factory = self._pending.pop(0)
            if op == "push" and factory is not None:
                self._stack.append(self._activate(factory))
            elif op == "pop":
                if self._stack:
                    self._deactivate(self._stack.pop())
            elif op == "replace" and factory is not None:
                if self._stack:
                    self._deactivate(self._stack.pop())
                self._stack.append(self._activate(factory))
            elif op == "set" and factory is not None:
                while self._stack:
                    self._deactivate(self._stack.pop())
                self._stack.append(self._activate(factory))

    def _activate(self, factory: SceneFactory) -> Scene:
        scene = factory()
        log.info("进入场景 %s", scene.scene_id)
        scene.enter()
        return scene

    @staticmethod
    def _deactivate(scene: Scene) -> None:
        log.info("离开场景 %s", scene.scene_id)
        try:
            scene.exit()
        except Exception:  # pragma: no cover - 退出不允许把进程带崩
            log.exception("场景 %s 退出时出错", scene.scene_id)

    # --- 每帧驱动 -----------------------------------------------------
    def update(self, dt: float) -> None:
        scene = self.top
        if scene is not None:
            scene.update(dt)
        self.flush()

    def handle_event(self, event) -> None:
        scene = self.top
        if scene is not None:
            scene.handle_event(event)

    def draw(self) -> None:
        scene = self.top
        if scene is not None:
            scene.draw()

    def shutdown(self) -> None:
        while self._stack:
            self._deactivate(self._stack.pop())
        self._pending.clear()
