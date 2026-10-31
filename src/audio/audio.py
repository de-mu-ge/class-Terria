"""音频服务。

本项目当前没有任何已登记的音频素材（见 assets/ASSETS.md 待办），因此：
- 音效与环境音用**程序化合成**生成（不依赖第三方素材，无授权问题）；
- 背景音乐在找不到文件时安静跳过，并记录缺口 —— 不崩溃、不静音整个游戏。

混音器初始化失败（无音频设备 / 沙盒）时整体退化为静音模式。
"""

from __future__ import annotations

import logging
import math
import random
import struct

from ..assets.paths import AssetPaths
from ..data.models import GameConfig

log = logging.getLogger(__name__)

_SAMPLE_RATE = 44100
_CHANNELS = 2


class AudioService:
    def __init__(self, config: GameConfig, paths: AssetPaths, enabled: bool = True) -> None:
        self._config = config
        self._paths = paths
        self._enabled = enabled and config.flag("audio", "enabled", default=True)
        self._mixer_ready = False
        self._sfx_cache: dict[str, object] = {}
        self._ambience_cache: dict[str, object] = {}
        self._ambient_channel = None
        self._ambient_id: str | None = None
        self._music_channel = None
        self._music_id: str | None = None
        self._master = float(config.number("audio", "master_volume", default=0.7))
        self._applied_volume = self._master
        self.missing_music: list[str] = []
        self._random = random.Random(20260101)

    # --- 初始化 -------------------------------------------------------
    def init(self) -> None:
        if not self._enabled:
            log.info("音频已禁用，进入静音模式")
            return
        try:
            import pygame

            pygame.mixer.pre_init(_SAMPLE_RATE, -16, _CHANNELS, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(12)
            self._ambient_channel = pygame.mixer.Channel(0)
            self._music_channel = pygame.mixer.Channel(1)
            self._mixer_ready = True
            log.info("音频混音器就绪（%d Hz）", _SAMPLE_RATE)
        except Exception as exc:  # pragma: no cover - 与设备相关
            log.warning("音频初始化失败，进入静音模式：%s", exc)
            self._mixer_ready = False

    # --- 音量 ---------------------------------------------------------
    @property
    def master_volume(self) -> float:
        return self._master

    def set_master_volume(self, value: float) -> None:
        self._master = max(0.0, min(1.0, float(value)))
        self._apply_volume()

    def _apply_volume(self) -> None:
        if not self._mixer_ready:
            return
        if abs(self._applied_volume - self._master) < 1e-3:
            return
        self._applied_volume = self._master
        try:
            for channel in (self._ambient_channel, self._music_channel):
                if channel is not None:
                    channel.set_volume(self._master)
        except Exception:  # pragma: no cover
            pass

    # --- 音效 ---------------------------------------------------------
    def play_sfx(self, sfx_id: str | None) -> None:
        if not sfx_id:
            return
        if not self._mixer_ready:
            return
        try:
            import pygame

            sound = self._sfx(sfx_id)
            if sound is None:
                return
            channel = pygame.mixer.find_channel(True)
            if channel is not None:
                channel.set_volume(self._master * 0.9)
                channel.play(sound)
        except Exception:  # pragma: no cover
            log.debug("音效播放失败：%s", sfx_id, exc_info=True)

    def _sfx(self, sfx_id: str):
        if sfx_id in self._sfx_cache:
            return self._sfx_cache[sfx_id]
        spec = self._config.value("audio", "sfx", sfx_id, default=None)
        if spec is None:
            log.warning("未定义的音效：%s", sfx_id)
            return None
        data = _synthesise(spec, self._random)
        sound = self._make_sound(data)
        self._sfx_cache[sfx_id] = sound
        return sound

    # --- 环境音 -------------------------------------------------------
    def play_ambience(self, ambience_id: str | None, volume: float = 1.0) -> None:
        if not ambience_id:
            return
        if not self._mixer_ready or self._ambient_channel is None:
            self._ambient_id = ambience_id
            return
        if self._ambient_id == ambience_id:
            return
        spec = self._config.value("audio", "ambience", ambience_id, default=None)
        if spec is None:
            log.warning("未定义的环境音：%s", ambience_id)
            return
        try:
            if ambience_id not in self._ambience_cache:
                self._ambience_cache[ambience_id] = self._make_sound(_synthesise(spec, self._random))
            sound = self._ambience_cache[ambience_id]
            self._ambient_channel.stop()
            self._ambient_channel.set_volume(self._master * float(spec.get("volume", 0.25)) * volume)
            self._ambient_channel.play(sound, loops=-1)
            self._ambient_id = ambience_id
        except Exception:  # pragma: no cover
            log.debug("环境音播放失败：%s", ambience_id, exc_info=True)

    def stop_ambience(self) -> None:
        self._ambient_id = None
        if self._mixer_ready and self._ambient_channel is not None:
            try:
                self._ambient_channel.stop()
            except Exception:  # pragma: no cover
                pass

    # --- 音乐 ---------------------------------------------------------
    def play_music(self, music_id: str | None, volume: float = 1.0) -> None:
        if not music_id or self._music_id == music_id:
            return
        self._music_id = music_id
        spec = self._config.value("audio", "music", music_id, default=None)
        if spec is None:
            log.warning("未定义的音乐：%s", music_id)
            return
        path = self._paths.audio(spec.get("file", ""))
        if not path.is_file():
            if music_id not in self.missing_music:
                self.missing_music.append(music_id)
                log.info("缺少音乐素材 %s（本轮跳过 BGM，环境音照常）", path.name)
            return
        if not self._mixer_ready or self._music_channel is None:
            return
        try:
            import pygame

            sound = pygame.mixer.Sound(str(path))
            self._music_channel.stop()
            self._music_channel.set_volume(self._master * float(spec.get("volume", 0.35)) * volume)
            self._music_channel.play(sound, loops=-1)
        except Exception:  # pragma: no cover
            log.warning("音乐播放失败：%s", path.name)

    def stop_music(self) -> None:
        self._music_id = None
        if self._mixer_ready and self._music_channel is not None:
            try:
                self._music_channel.stop()
            except Exception:  # pragma: no cover
                pass

    def stop_all(self) -> None:
        self.stop_ambience()
        self.stop_music()

    # --- 内部 ---------------------------------------------------------
    def _make_sound(self, raw: bytes):
        import pygame

        return pygame.mixer.Sound(buffer=raw)

    def shutdown(self) -> None:
        self.stop_all()
        if self._mixer_ready:
            try:
                import pygame

                pygame.mixer.quit()
            except Exception:  # pragma: no cover
                pass
            self._mixer_ready = False


# --- 合成 -----------------------------------------------------------------
def _synthesise(spec: dict, rng: random.Random) -> bytes:
    kind = str(spec.get("type", "tone"))
    duration = float(spec.get("duration", 0.1))
    volume = float(spec.get("volume", 0.3))
    frames = max(1, int(_SAMPLE_RATE * duration))
    samples = [0.0] * frames

    if kind == "tone":
        freq = float(spec.get("freq", 440))
        wave = str(spec.get("wave", "sine"))
        decay = float(spec.get("decay", 6.0))
        for i in range(frames):
            t = i / _SAMPLE_RATE
            phase = 2.0 * math.pi * freq * t
            if wave == "square":
                value = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "triangle":
                value = 2.0 / math.pi * math.asin(math.sin(phase))
            else:
                value = math.sin(phase)
            envelope = math.exp(-decay * t) if decay > 0 else 1.0
            # 两端各 4ms 淡入淡出，避免爆音
            edge = min(1.0, i / (_SAMPLE_RATE * 0.004) + 1e-6,
                       (frames - i) / (_SAMPLE_RATE * 0.004) + 1e-6)
            samples[i] = value * envelope * edge * volume
    else:  # noise
        lowpass = float(spec.get("lowpass", 0.4))
        decay = float(spec.get("decay", 0.0))
        swell_hz = float(spec.get("swell_hz", 0.0))
        swell_depth = float(spec.get("swell_depth", 0.0))
        state = 0.0
        for i in range(frames):
            white = rng.uniform(-1.0, 1.0)
            state += (white - state) * lowpass
            value = state
            t = i / _SAMPLE_RATE
            envelope = 1.0
            if decay > 0:
                envelope = math.exp(-decay * t)
            if swell_hz > 0:
                envelope *= 1.0 - swell_depth * 0.5 * (1.0 + math.sin(2.0 * math.pi * swell_hz * t))
                env_edge = min(1.0, t / 0.5, (duration - t) / 0.5)
                envelope *= max(0.0, env_edge)
            samples[i] = value * envelope * volume

    # 归一化到 int16，双声道
    peak = max(1e-6, max(abs(s) for s in samples))
    gain = min(1.0, 0.92 / peak) if peak > 0.92 else 1.0
    out = bytearray()
    for s in samples:
        value = int(max(-1.0, min(1.0, s * gain)) * 32767)
        packed = struct.pack("<h", value)
        out += packed
        out += packed
    return bytes(out)
