"""固定时间步长主循环。

- 逻辑更新固定 dt（默认 1/60），保证不同帧率下演出时长一致。
- 渲染每帧一次。
- 时间来源、事件轮询、更新、绘制全部由外部注入，便于无窗口测试。
"""

from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)


class FixedTimestepLoop:
    def __init__(
        self,
        update: Callable[[float], None],
        render: Callable[[], None],
        poll: Callable[[], None],
        should_continue: Callable[[], bool],
        time_source: Callable[[], float],
        fixed_dt: float = 1.0 / 60.0,
        time_scale: float = 1.0,
        max_frame_time: float = 0.1,
        max_update_steps: int = 6,
    ) -> None:
        self._update = update
        self._render = render
        self._poll = poll
        self._should_continue = should_continue
        self._time = time_source
        self.fixed_dt = max(1e-4, fixed_dt)
        self.time_scale = max(0.0, time_scale)
        self.max_frame_time = max_frame_time
        self.max_update_steps = max(1, max_update_steps)
        self.frames = 0

    def run(self) -> int:
        last = self._time()
        accumulator = 0.0
        log.debug("主循环启动：fixed_dt=%.4f time_scale=%.2f", self.fixed_dt, self.time_scale)
        while self._should_continue():
            now = self._time()
            frame_time = now - last
            last = now
            if frame_time < 0:
                frame_time = 0.0
            frame_time = min(frame_time, self.max_frame_time)

            self._poll()

            accumulator += frame_time * self.time_scale
            steps = 0
            while accumulator >= self.fixed_dt and steps < self.max_update_steps:
                self._update(self.fixed_dt)
                accumulator -= self.fixed_dt
                steps += 1
            if steps >= self.max_update_steps:
                # 落后太多就丢弃积压，避免“螺旋死亡”
                accumulator = 0.0

            self._render()
            self.frames += 1
        log.debug("主循环结束，共 %d 帧", self.frames)
        return self.frames
