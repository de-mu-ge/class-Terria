"""通用有限状态机。

用于应用级状态（标题 / 游戏 / 退出）与 UI 内部状态（打字中 / 等待输入 / 结束），
避免在各处散落 if-else 判断当前阶段。
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Iterable, List

Hook = Callable[[], None]


class StateMachine:
    def __init__(self, name: str, initial: str, states: Iterable[str]) -> None:
        self._name = name
        self._states = list(states)
        if initial not in self._states:
            raise ValueError(f"[{name}] 初始状态 {initial!r} 不在状态集合内")
        self._state = initial
        self._previous: str | None = None
        self._elapsed = 0.0
        self._enter_hooks: Dict[str, List[Hook]] = {}
        self._exit_hooks: Dict[str, List[Hook]] = {}
        self._log = logging.getLogger(f"state.{name}")

    # --- 查询 ---------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def previous(self) -> str | None:
        return self._previous

    @property
    def elapsed(self) -> float:
        """进入当前状态后经过的秒数。"""
        return self._elapsed

    def is_state(self, *names: str) -> bool:
        return self._state in names

    def has_state(self, name: str) -> bool:
        return name in self._states

    # --- 钩子 ---------------------------------------------------------
    def on_enter(self, state: str, hook: Hook) -> None:
        self._enter_hooks.setdefault(state, []).append(hook)

    def on_exit(self, state: str, hook: Hook) -> None:
        self._exit_hooks.setdefault(state, []).append(hook)

    # --- 驱动 ---------------------------------------------------------
    def transition(self, target: str, force: bool = False) -> bool:
        if target not in self._states:
            raise ValueError(f"[{self._name}] 未知状态 {target!r}（可用：{self._states}）")
        if target == self._state and not force:
            return False
        for hook in self._exit_hooks.get(self._state, []):
            hook()
        self._previous = self._state
        self._state = target
        self._elapsed = 0.0
        self._log.debug("→ %s", target)
        for hook in self._enter_hooks.get(target, []):
            hook()
        return True

    def update(self, dt: float) -> None:
        self._elapsed += dt

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"StateMachine({self._name}, state={self._state!r})"
