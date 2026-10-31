"""演出导演：把 data/scenes.json 的指令翻译成具体动作。

分工：
- Director  = 解释指令 + 持有舞台/UI 状态
- Task      = 一段需要等待完成的演出（淡入、对话、摇晃……）
- 瞬时指令  = 直接改状态，不占用时间线（切表情、播 SFX、显示 HUD……）

代码里不出现任何台词：文本一律从 DataRepository 读。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from ..core.context import SceneContext
from ..core.events import InputEvent, InputKind
from ..core.timeline import Task, Timeline, TimerTask, clamp01
from ..core.types import parse_color
from ..data.models import Character, DialogueBlock, Line, SceneSpec
from ..render.renderer import Texture
from ..ui.chat import ChatView
from ..ui.dialogue_box import DialogueView
from ..ui.hud import Hud, SignalWidget
from ..ui.info_panels import HintPanel, TaskPanel
from ..ui.photo import PhotoView
from ..ui.particles import ParticleField
from ..ui.subtitle import SubtitleBar
from ..ui.transitions import Fade, Flash, GradientMask
from .effects import FishJump
from .stage import (
    Animator,
    Camera,
    CameraAnimator,
    DollAnimator,
    DollLayer,
    PixelActor,
    ShakeAnimator,
    MaskAnimator,
    BackgroundLayer,
)

log = logging.getLogger(__name__)


# --- Task 包装 -------------------------------------------------------------
class AnimatorTask(Task):
    def __init__(self, animator: Animator) -> None:
        self.animator = animator

    def on_start(self) -> None:
        self.animator.update(0.0)

    def update(self, dt: float) -> bool:
        return self.animator.update(dt)

    def finish_now(self) -> None:
        self.animator.update(self.animator.duration + 1.0)


class DialogueTask(Task):
    def __init__(self, director: "Director", block: DialogueBlock) -> None:
        self._director = director
        self._block = block
        self._auto_timer = 0.0

    def on_start(self) -> None:
        self._director.start_dialogue(self._block)

    def update(self, dt: float) -> bool:
        director = self._director
        view = director.dialogue
        if director.autoplay and view.active:
            self._auto_timer += dt
            if view.typing:
                view.advance()
            elif view.waiting and self._auto_timer > 0.2:
                self._auto_timer = 0.0
                view.advance()
        return view.closed

    def handle_event(self, event: InputEvent) -> bool:
        return self._director.dialogue.handle_event(event)


class ChatTask(Task):
    def __init__(self, director: "Director", command: dict[str, Any]) -> None:
        self._director = director
        self._command = command

    def on_start(self) -> None:
        cmd = self._command
        self._director.chat.start(
            title=str(cmd.get("title", "")),
            messages=list(cmd.get("messages", [])),
            per_message=float(cmd.get("per_message", 0.9)),
            hold=float(cmd.get("hold", 2.0)),
            sound=cmd.get("sound", "message_ping"),
        )

    def update(self, dt: float) -> bool:
        return self._director.chat.done

    def finish_now(self) -> None:
        self._director.chat.fail()


class SubtitleTask(Task):
    def __init__(self, director: "Director", command: dict[str, Any]) -> None:
        self._director = director
        self._command = command

    def on_start(self) -> None:
        cmd = self._command
        self._director.subtitle.show(
            str(cmd.get("text", "")),
            label=cmd.get("label"),
            duration=float(cmd.get("duration", 6.0)),
        )

    def update(self, dt: float) -> bool:
        return self._director.subtitle.done


class PhotoTask(Task):
    def __init__(self, director: "Director", command: dict[str, Any]) -> None:
        self._director = director
        self._command = command

    def on_start(self) -> None:
        self._director.start_photo(self._command)

    def update(self, dt: float) -> bool:
        return self._director.photo.done


class EffectTask(Task):
    def __init__(self, director: "Director", effect) -> None:
        self._director = director
        self.effect = effect
        self.elapsed = 0.0
        self.duration = effect.duration

    def on_start(self) -> None:
        self._director.add_effect(self.effect)

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        return self.elapsed >= self.duration


class ShakeTask(Task):
    def __init__(self, director: "Director", animator: ShakeAnimator) -> None:
        self._director = director
        self.animator = animator

    def on_start(self) -> None:
        self._director.set_shake(self.animator)

    def update(self, dt: float) -> bool:
        return self.animator.update(dt)

    def finish_now(self) -> None:
        self.animator.update(self.animator.duration + 1.0)


class MaskTask(Task):
    def __init__(self, director: "Director", animator: MaskAnimator) -> None:
        self._director = director
        self.animator = animator

    def on_start(self) -> None:
        self._director.add_animator(self.animator)

    def update(self, dt: float) -> bool:
        return self.animator.done


# --- 导演 -----------------------------------------------------------------
class Director:
    def __init__(self, ctx: SceneContext, spec: SceneSpec,
                 on_complete: Callable[[str], None] | None = None) -> None:
        self.ctx = ctx
        self.spec = spec
        self._on_complete = on_complete

        self.bg = BackgroundLayer(ctx)
        self.dolls = DollLayer(ctx)
        self.sprite: PixelActor | None = None
        self.dialogue = DialogueView(ctx, on_line=self._on_line)
        self.chat = ChatView(ctx)
        self.subtitle = SubtitleBar(ctx)
        self.photo = PhotoView(ctx)
        self.overlay_mask: GradientMask | None = None
        self.particles = None  # 粒子演出（樱花 / 雨 / 雾 / 浪花），由 _cmd_particles 创建
        self.hud = Hud(ctx)
        self.signal = SignalWidget(ctx)
        self.task_panel = TaskPanel(ctx)
        self.hint_panel = HintPanel(ctx)

        self.pipeline = spec.pipeline
        self.fast_forward = False
        self.autoplay = False
        self.finished = False
        self.end_kind = "next"

        # 像素段落一开始就把 Sprite 建好（否则第一帧会没有人）
        if self.pipeline == "pixel":
            character = self._speaker_character("anon")
            if character is not None:
                self.sprite = PixelActor(self.ctx, character)

        self._animators: list[Animator] = []
        self._effects: list[Any] = []
        self._shake: ShakeAnimator | None = None
        self._screen: Fade | Flash | None = None
        self._screen_task: Task | None = None
        self._speaker: str | None = None
        self._debug = ctx.debug

        # 场景初始音乐 / 环境音
        if spec.music:
            ctx.audio.play_music(spec.music)
        if spec.ambience:
            ctx.audio.play_ambience(spec.ambience)

        self.timeline = Timeline(spec.timeline, self.begin, on_complete=self._on_timeline_complete)

    # --- 时间线 -------------------------------------------------------
    def begin(self, command: dict[str, Any]) -> Task | None:
        cmd = command.get("cmd")
        handler = getattr(self, f"_cmd_{cmd}", None)
        if handler is None:
            log.error("未知指令：%s（场景 %s）", cmd, self.spec.id)
            return None
        return handler(command)

    def update(self, dt: float) -> None:
        for animator in list(self._animators):
            if animator.update(dt) and animator.done:
                if animator in self._animators:
                    self._animators.remove(animator)
        for effect in list(self._effects):
            effect.update(dt)
            if effect.done:
                self._effects.remove(effect)
        if self._shake is not None and self._shake.done:
            self._shake = None
        self.bg.update(dt)
        self.dialogue.update(dt, self.fast_forward)
        if not self.dialogue.active:
            self._speaker = None
        self.chat.update(dt)
        self.subtitle.update(dt)
        self.photo.update(dt)
        if self.sprite is not None:
            self.sprite.update(dt)
        if self.particles is not None:
            self.particles.update(dt)
            if not self.particles.active:
                self.particles = None
        self.hud.update(dt)
        self.signal.update(dt)
        self.task_panel.update(dt)
        self.hint_panel.update(dt)
        if self._screen is not None:
            self._screen.update(dt)
            if self._screen.done and self._screen.alpha == 0:
                self._screen = None
        self.timeline.update(dt)

    def handle_event(self, event: InputEvent) -> bool:
        if event.kind == InputKind.FAST_FORWARD_START:
            self.fast_forward = True
            return True
        if event.kind == InputKind.FAST_FORWARD_END:
            self.fast_forward = False
            return True
        return self.timeline.handle_event(event)

    def _on_timeline_complete(self) -> None:
        if self.finished:
            return
        self.finished = True
        if self._on_complete:
            self._on_complete(self.end_kind)

    # --- 绘制 ---------------------------------------------------------
    def draw(self) -> None:
        renderer = self.ctx.renderer
        renderer.clear(parse_color(self.ctx.config.color("black")))
        offset = self._shake.offset if self._shake is not None else (0.0, 0.0)

        self.bg.draw(renderer, offset=offset)
        if self.pipeline == "pixel":
            if self.sprite is not None:
                self.sprite.draw(renderer, offset=offset)
        else:
            self.dolls.draw(renderer, active_speaker=self._speaker, offset=offset)

        # 粒子在人物之后、遮罩之前：花瓣要“从镜头前飘过”
        if self.particles is not None:
            self.particles.draw(renderer)

        for effect in self._effects:
            effect.draw(renderer, offset=offset)

        if self.overlay_mask is not None:
            self.overlay_mask.draw()

        self.hud.draw()
        self.signal.draw()
        self.subtitle.draw()
        self.task_panel.draw()
        self.dialogue.draw()
        self.chat.draw()
        self.photo.draw()
        self.hint_panel.draw()
        if self._screen is not None:
            self._screen.draw()
        if self._debug:
            self._draw_debug()

    def _draw_debug(self) -> None:
        renderer = self.ctx.renderer
        font = self.ctx.resources.font("debug")
        cam = self.bg.camera
        text = (f"{self.spec.id} | pipeline={self.pipeline} | zoom={cam.zoom:.2f} "
                f"focus={cam.focus[0]:.2f},{cam.focus[1]:.2f} | cmd={self.timeline.command_index}")
        renderer.draw_text(text, (8, 8), font, self.ctx.config.color("warm_core"))
        if self.dialogue.current_line is not None:
            action = self.dialogue.current_line.action
            if action:
                renderer.draw_text(f"[动作] {action}", (8, 24), font,
                                   self.ctx.config.color("text_dim"))

    # --- 对话回调 -----------------------------------------------------
    def _speaker_character(self, char_id: str) -> Character | None:
        try:
            return self.ctx.data.character(char_id)
        except Exception:
            return None

    def _on_line(self, line: Line) -> None:
        self._speaker = line.speaker
        if line.sfx:
            self.ctx.audio.play_sfx(line.sfx)
        if line.pose and self.sprite is not None:
            self.sprite.set_pose(str(line.pose))
        if line.portrait:
            self.dolls.set_portrait(line.speaker, line.portrait)
        if line.camera:
            self._apply_line_camera(line.camera)

    def _apply_line_camera(self, camera_spec: Any) -> None:
        presets = self.ctx.config.value("camera", "presets", default={}) or {}
        if isinstance(camera_spec, str):
            preset = presets.get(camera_spec)
            if preset is None:
                log.warning("未知镜头预设：%s", camera_spec)
                return
            duration = float(preset.get("duration", 0.8))
            target = Camera(
                zoom=self.bg.camera.zoom * float(preset.get("zoom_mul", 1.0)),
                focus=self.bg.camera.focus,
            )
            ease = str(preset.get("ease", "out"))
        elif isinstance(camera_spec, dict):
            duration = float(camera_spec.get("duration", 0.8))
            target = Camera(
                zoom=float(camera_spec.get("zoom", self.bg.camera.zoom)),
                focus=tuple(camera_spec.get("focus", self.bg.camera.focus)),  # type: ignore[arg-type]
            )
            ease = str(camera_spec.get("ease", "out"))
        else:
            return
        self.add_animator(CameraAnimator(self.bg, target, duration, ease))

    def start_dialogue(self, block: DialogueBlock) -> None:
        self._speaker = None
        self.dialogue.start(block)
        line = self.dialogue.current_line
        if line is not None:
            self._speaker = line.speaker

    # --- 指令实现（瞬时/阻塞由返回值决定） ----------------------------
    def _cmd_sfx(self, command: dict[str, Any]) -> Task | None:
        self.ctx.audio.play_sfx(command.get("id"))
        return None

    def _cmd_wait(self, command: dict[str, Any]) -> Task | None:
        duration = float(command.get("duration", 0.0))
        return TimerTask(duration) if duration > 0 else None

    def _cmd_fade_in(self, command: dict[str, Any]) -> Task | None:
        duration = float(command.get("duration", self.ctx.config.number("transitions", "fade_in", default=0.6)))
        fade = Fade(self.ctx.renderer, self.ctx.config.color("black"), 255, 0, duration, "out")
        self._screen = fade
        return AnimatorTask(_FadeAnimator(fade))

    def _cmd_fade_out(self, command: dict[str, Any]) -> Task | None:
        duration = float(command.get("duration", self.ctx.config.number("transitions", "fade_out", default=0.5)))
        fade = Fade(self.ctx.renderer, self.ctx.config.color("black"), 0, 255, duration, "in_out")
        self._screen = fade
        return AnimatorTask(_FadeAnimator(fade))

    def _cmd_black(self, command: dict[str, Any]) -> Task | None:
        duration = float(command.get("duration", 1.0))
        fade = Fade(self.ctx.renderer, self.ctx.config.color("black"), 255, 255, max(0.001, duration))
        self._screen = fade
        return AnimatorTask(_FadeAnimator(fade))

    def _cmd_flash(self, command: dict[str, Any]) -> Task | None:
        duration = float(command.get("duration", self.ctx.config.number("transitions", "flash", default=0.15)))
        flash = Flash(self.ctx.renderer, self.ctx.config.color("white"), duration)
        self._screen = flash
        return AnimatorTask(_FlashAnimator(flash))

    def _cmd_bg(self, command: dict[str, Any]) -> Task | None:
        bg_id = command.get("id")
        spec = self.spec.background(bg_id) if bg_id else None
        if spec is None:
            log.error("场景 %s 缺少背景 %s", self.spec.id, bg_id)
            return None
        texture = self.ctx.resources.texture(self.ctx.paths.background(spec.file))
        camera = self._camera_from(command.get("camera"), default_focus=True)
        transition = str(command.get("transition", "cut"))
        duration = float(command.get("duration", self.ctx.config.number("transitions", "scene", default=0.4)))
        if transition == "crossfade":
            self.bg.set(texture, camera, smooth=spec.smooth, crossfade=duration)
            return TimerTask(duration)
        self.bg.set(texture, camera, smooth=spec.smooth)
        return None

    def _camera_from(self, value: Any, default_focus: bool = False, base: Camera | None = None) -> Camera:
        base = base or self.bg.camera
        if isinstance(value, dict):
            focus = value.get("focus", base.focus)
            return Camera(zoom=float(value.get("zoom", base.zoom)),
                          focus=(float(focus[0]), float(focus[1])))
        if default_focus:
            return Camera(zoom=base.zoom, focus=base.focus)
        return base.copy()

    def _cmd_camera(self, command: dict[str, Any]) -> Task | None:
        duration = command.get("duration")
        ease = str(command.get("ease", "out"))
        if "preset" in command:
            presets = self.ctx.config.value("camera", "presets", default={}) or {}
            preset = presets.get(str(command["preset"]))
            if preset is None:
                log.warning("未知镜头预设：%s", command["preset"])
                return None
            duration = float(duration if duration is not None else preset.get("duration", 0.8))
            target = Camera(zoom=clamp(self.bg.camera.zoom * float(preset.get("zoom_mul", 1.0)), 0.3, 4.0),
                            focus=self.bg.camera.focus)
            ease = str(preset.get("ease", ease))
        else:
            source = command.get("from")
            target_camera = command.get("to")
            if target_camera is None:
                return None
            target = self._camera_from(target_camera)
            duration = float(duration if duration is not None else 1.0)
            if source is not None:
                self.bg.camera = self._camera_from(source)
        animator = CameraAnimator(self.bg, target, float(duration), ease)
        self.add_animator(animator)
        return AnimatorTask(animator)

    def _cmd_doll_show(self, command: dict[str, Any]) -> Task | None:
        char_id = str(command.get("char", ""))
        character = self._speaker_character(char_id)
        if character is None:
            log.error("doll_show 引用了不存在的角色：%s", char_id)
            return None
        base_height = float(command.get("height", self.ctx.config.number("stage", "doll_base_height", default=450)))
        x = float(command.get("x", self.ctx.renderer.width / 2))
        bottom = float(command.get("bottom", self.ctx.renderer.height))
        duration = float(command.get("duration", 0.6))
        enter = str(command.get("enter", "fade"))
        flip = bool(command.get("flip", False))
        portrait = command.get("doll") or command.get("portrait")
        start_x = x
        if enter == "slide_from_right":
            start_x = x + 360.0
        elif enter == "slide_from_left":
            start_x = x - 360.0
        doll = self.dolls.show(character, portrait, start_x, bottom, base_height,
                               alpha=0.0 if enter != "none" else 1.0, flip=flip)
        if enter == "none" or duration <= 0.0:
            doll.x = x
            doll.alpha = 1.0
            return None
        animator = DollAnimator(doll, {"x": x, "alpha": 1.0}, duration, "out")
        self.add_animator(animator)
        return AnimatorTask(animator)

    def _cmd_doll_hide(self, command: dict[str, Any]) -> Task | None:
        char_id = str(command.get("char", ""))
        doll = self.dolls.get(char_id)
        if doll is None:
            return None
        duration = float(command.get("duration", 0.3))
        animator = DollAnimator(doll, {"alpha": 0.0}, duration, "in_out", remove_on_finish=True)
        self.add_animator(animator)

        def _cleanup() -> None:
            if doll.alpha <= 0.01:
                self.dolls.hide(char_id)

        return TimerTask(duration, on_done=_cleanup)

    def _cmd_doll_portrait(self, command: dict[str, Any]) -> Task | None:
        char_id = str(command.get("char", ""))
        portrait = command.get("doll") or command.get("portrait")
        self.dolls.set_portrait(char_id, portrait)
        return None

    def _cmd_doll_move(self, command: dict[str, Any]) -> Task | None:
        char_id = str(command.get("char", ""))
        doll = self.dolls.get(char_id)
        if doll is None:
            return None
        target: dict[str, float] = {}
        for key in ("x", "bottom", "height", "alpha"):
            if key in command:
                target[key] = float(command[key])
        duration = float(command.get("duration", 0.6))
        ease = str(command.get("ease", "out"))
        animator = DollAnimator(doll, target, duration, ease)
        self.add_animator(animator)
        return AnimatorTask(animator)

    def _cmd_sprite(self, command: dict[str, Any]) -> Task | None:
        char_id = str(command.get("char", "anon"))
        character = self._speaker_character(char_id)
        if character is None:
            return None
        if self.sprite is None:
            self.sprite = PixelActor(self.ctx, character)
        if "pose" in command:
            self.sprite.set_pose(str(command["pose"]))
        if "x" in command:
            self.sprite.x = float(command["x"])
        if "ground_y" in command:
            self.sprite.ground_y = float(command["ground_y"])
        if "scale" in command:
            self.sprite.scale = float(command["scale"])
        if "flip" in command:
            self.sprite.flip = bool(command["flip"])
        if "alpha" in command:
            self.sprite.alpha = clamp01(float(command["alpha"]))
        return None

    def _cmd_dialogue(self, command: dict[str, Any]) -> Task | None:
        block_id = str(command.get("block", ""))
        try:
            block = self.ctx.data.dialogue_block(block_id)
        except Exception:
            log.exception("找不到台词段：%s", block_id)
            return None
        return DialogueTask(self, block)

    def _cmd_chat(self, command: dict[str, Any]) -> Task | None:
        return ChatTask(self, command)

    def _cmd_subtitle(self, command: dict[str, Any]) -> Task | None:
        return SubtitleTask(self, command)

    def _cmd_subtitle_hide(self, command: dict[str, Any]) -> Task | None:
        self.subtitle.hide()
        return TimerTask(0.3)

    def _cmd_signal(self, command: dict[str, Any]) -> Task | None:
        self.signal.set_state(str(command.get("state", "ok")))
        return None

    def _cmd_signal_hide(self, command: dict[str, Any]) -> Task | None:
        self.signal.hide()
        return None

    def _cmd_tint(self, command: dict[str, Any]) -> Task | None:
        top = parse_color(command.get("top", self.ctx.config.color("weather_overcast")))
        bottom = parse_color(command.get("bottom", self.ctx.config.color("mid")))
        top_alpha = int(command.get("top_alpha", 210))
        bottom_alpha = int(command.get("bottom_alpha", 90))
        duration = float(command.get("duration", 4.0))
        previous = self.overlay_mask.strength if self.overlay_mask is not None else 0.0
        # 允许换一套遮罩颜色（例如“晴转阴”之后“船舱灯全灭”），并保持当前浓度不跳变
        self.overlay_mask = GradientMask(self.ctx.renderer, top, bottom, top_alpha, bottom_alpha, 0.0)
        self.overlay_mask.set_strength(previous)
        target = float(command.get("strength", 1.0))
        animator = MaskAnimator(self.overlay_mask, target, duration, str(command.get("ease", "out")))
        return MaskTask(self, animator)

    def _cmd_tint_clear(self, command: dict[str, Any]) -> Task | None:
        if self.overlay_mask is None:
            return None
        animator = MaskAnimator(self.overlay_mask, 0.0, float(command.get("duration", 1.0)))
        return MaskTask(self, animator)

    def _cmd_shake(self, command: dict[str, Any]) -> Task | None:
        defaults = self.ctx.config.section("stage").get("shake_default", {})
        amplitude = float(command.get("amplitude", defaults.get("amplitude", 2.5)))
        frequency = float(command.get("frequency", defaults.get("frequency", 0.5)))
        duration = command.get("duration")
        animator = ShakeAnimator(amplitude, frequency,
                                 float(duration) if duration is not None else None)
        if duration is None:
            self.set_shake(animator)
            return None
        return ShakeTask(self, animator)

    def _cmd_shake_stop(self, command: dict[str, Any]) -> Task | None:
        self._shake = None
        return None

    def _cmd_photo(self, command: dict[str, Any]) -> Task | None:
        return PhotoTask(self, command)

    def _cmd_pipeline(self, command: dict[str, Any]) -> Task | None:
        new_pipeline = str(command.get("id", "galgame"))
        self.pipeline = new_pipeline
        if new_pipeline == "pixel":
            character = self._speaker_character(str(command.get("char", "anon")))
            if character is None:
                return None
            if self.sprite is None:
                self.sprite = PixelActor(self.ctx, character)
                self.sprite.alpha = float(command.get("alpha", 1.0))
            if "pose" in command:
                self.sprite.set_pose(str(command["pose"]))
            if "x" in command:
                self.sprite.x = float(command["x"])
            if "ground_y" in command:
                self.sprite.ground_y = float(command["ground_y"])
            if "alpha" in command:
                self.sprite.alpha = clamp01(float(command["alpha"]))
        return None

    def _cmd_hud(self, command: dict[str, Any]) -> Task | None:
        if command.get("visible", True):
            self.hud.show()
        else:
            self.hud.hide()
        if "life" in command:
            self.hud.set_values(life=float(command["life"]))
        if "temp" in command:
            self.hud.set_values(temp=float(command["temp"]))
        return None

    def _cmd_hint(self, command: dict[str, Any]) -> Task | None:
        if command.get("visible", True):
            self.hint_panel.show(str(command.get("title", "")), list(command.get("lines", [])))
        else:
            self.hint_panel.hide()
        return None

    def _cmd_task(self, command: dict[str, Any]) -> Task | None:
        if command.get("visible", True):
            rows = [(str(pair[0]), str(pair[1])) for pair in command.get("rows", [])]
            self.task_panel.show(str(command.get("title", "")), rows)
        else:
            self.task_panel.hide()
        return None

    def _cmd_music(self, command: dict[str, Any]) -> Task | None:
        music_id = command.get("id")
        if music_id in (None, "", "none", "stop"):
            self.ctx.audio.stop_music()
            return None
        self.ctx.audio.play_music(str(music_id), float(command.get("volume", 1.0)))
        return None

    def _cmd_ambience(self, command: dict[str, Any]) -> Task | None:
        if command.get("id") in (None, "none", ""):
            self.ctx.audio.stop_ambience()
        else:
            self.ctx.audio.play_ambience(str(command["id"]), float(command.get("volume", 1.0)))
        return None

    def _cmd_effect(self, command: dict[str, Any]) -> Task | None:
        effect_id = str(command.get("id", ""))
        if effect_id == "fish_jump":
            effect = FishJump(
                x0=float(command.get("x0", 420)),
                x1=float(command.get("x1", 700)),
                y0=float(command.get("y0", 300)),
                height=float(command.get("height", 46)),
                duration=float(command.get("duration", 1.1)),
                color=self.ctx.config.color("cold_white"),
            )
            return EffectTask(self, effect)
        log.warning("未知特效：%s", effect_id)
        return None

    def _cmd_particles(self, command: dict[str, Any]) -> Task | None:
        preset = command.get("preset")
        if preset in (None, "", "none", "off", "stop"):
            if self.particles is not None:
                self.particles.stop()
            return None
        name = str(preset)
        if self.particles is not None and self.particles.name == name:
            return None
        try:
            self.particles = ParticleField(self.ctx, name)
        except ValueError:
            log.exception("粒子预设不存在：%s", name)
        return None

    def _cmd_end(self, command: dict[str, Any]) -> Task | None:
        self.end_kind = "next"
        return None

    def _cmd_handoff(self, command: dict[str, Any]) -> Task | None:
        self.end_kind = "handoff"
        return None

    # --- 辅助 ---------------------------------------------------------
    def add_animator(self, animator: Animator) -> None:
        self._animators.append(animator)

    def add_effect(self, effect) -> None:
        self._effects.append(effect)

    def set_shake(self, animator: ShakeAnimator | None) -> None:
        self._shake = animator

    def start_photo(self, command: dict[str, Any]) -> None:
        bg_id = command.get("bg")
        texture: Texture | None = self.bg.texture
        if bg_id:
            spec = self.spec.background(str(bg_id))
            if spec is not None:
                texture = self.ctx.resources.texture(self.ctx.paths.background(spec.file))
        cast: list[tuple[Character, str | None, float]] = []
        for index, entry in enumerate(command.get("cast", [])):
            char_id = str(entry.get("char", ""))
            character = self._speaker_character(char_id)
            if character is None:
                continue
            ratio = float(entry.get("x", 0.16 + index * 0.17))
            cast.append((character, entry.get("doll"), ratio))
        self.photo.show(texture, str(command.get("caption", "")), cast,
                        duration=float(command.get("duration", 2.0)))

    def stop_all_ui(self) -> None:
        self.dialogue.hide_immediately()
        self.chat.fail()
        self.subtitle.hide_immediately()
        self.photo.hide()
        self.hint_panel.hide()
        self.task_panel.hide()
        self.hud.hide()
        self.signal.hide()
        if self.particles is not None:
            self.particles.stop()


# --- 过场遮罩适配器 -------------------------------------------------------
class _FadeAnimator(Animator):
    def __init__(self, fade: Fade) -> None:
        super().__init__(max(0.001, fade.duration))
        self._fade = fade

    def update(self, dt: float) -> bool:
        return self._fade.update(dt)


class _FlashAnimator(Animator):
    def __init__(self, flash: Flash) -> None:
        super().__init__(max(0.001, flash.duration))
        self._flash = flash

    def update(self, dt: float) -> bool:
        return self._flash.update(dt)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
