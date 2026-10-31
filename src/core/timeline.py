"""时间线：把 data/scenes.json 里的演出指令变成可推进的步骤序列。

每个指令交给 begin() 回调，回调可选择返回一个 Task：
    - 返回 Task：时间线等它 done 再走下一步（淡入淡出、对话、镜头、摇晃……）
    - 返回 None：瞬时指令，立刻走下一步（切换背景图、切表情、播 SFX……）
"""

from __future__ import annotations

from abc import ABC
from typing import Callable, List, Sequence

from .events import InputEvent

Command = dict


class Task(ABC):
    """一个演出步骤。"""

    def on_start(self) -> None:
        pass

    def update(self, dt: float) -> bool:
        """返回 True 表示完成。"""
        return True

    def handle_event(self, event: InputEvent) -> bool:
        """返回 True 表示事件已被消费。"""
        return False

    def skip(self) -> None:
        """快进到底（仍会保留最终视觉状态）。"""
        self.finish_now()

    def finish_now(self) -> None:
        pass


class NullTask(Task):
    pass


class TimerTask(Task):
    def __init__(self, duration: float, on_start: Callable[[], None] | None = None,
                 on_done: Callable[[], None] | None = None) -> None:
        self.duration = max(0.0, duration)
        self.elapsed = 0.0
        self._on_start = on_start
        self._on_done = on_done
        self._started = False
        self._done = False

    def on_start(self) -> None:
        self._started = True
        if self._on_start:
            self._on_start()

    def update(self, dt: float) -> bool:
        if self._done:
            return True
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self._complete()
            return True
        return False

    def finish_now(self) -> None:
        if not self._done:
            self.elapsed = self.duration
            self._complete()

    def _complete(self) -> None:
        self._done = True
        if self._on_done:
            self._on_done()


class Timeline:
    def __init__(
        self,
        commands: Sequence[Command],
        begin: Callable[[Command], Task | None],
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self._commands: List[Command] = list(commands)
        self._begin = begin
        self._on_complete = on_complete
        self._index = 0
        self._task: Task | None = None
        self._done = False
        self._command_index = 0  # 当前正在执行的指令下标（调试/存档用）

    @property
    def done(self) -> bool:
        return self._done

    @property
    def command_index(self) -> int:
        return self._command_index

    def update(self, dt: float) -> None:
        if self._done:
            return
        guard = 0
        while True:
            guard += 1
            if guard > 4096:  # 防御：瞬时指令死循环保护
                raise RuntimeError("时间线瞬时指令数量异常，疑似循环")
            if self._task is None:
                if self._index >= len(self._commands):
                    self._done = True
                    if self._on_complete:
                        self._on_complete()
                    return
                command = self._commands[self._index]
                self._command_index = self._index
                self._index += 1
                task = self._begin(command)
                if task is None:
                    continue
                self._task = task
                task.on_start()
            if self._task.update(dt):
                self._task = None
                continue
            return

    def handle_event(self, event: InputEvent) -> bool:
        if self._task is not None:
            return self._task.handle_event(event)
        return False

    def skip(self) -> None:
        """把当前步骤快进到底（不会跳过后续步骤）。"""
        if self._task is not None:
            self._task.skip()


# --- 缓动 -----------------------------------------------------------------
def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_linear(t: float) -> float:
    return clamp01(t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return t * t * (3.0 - 2.0 * t)


EASINGS = {
    "linear": ease_linear,
    "out": ease_out_cubic,
    "in_out": ease_in_out,
}


def easing(name: str | None) -> Callable[[float], float]:
    return EASINGS.get(name or "linear", ease_linear)
