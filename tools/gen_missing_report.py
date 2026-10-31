"""生成《缺图清单.md》：把 --check-assets 的结果按「角色 × 表情 × 场景」整理成可交办的清单。

用法：python tools/gen_missing_report.py
"""

from __future__ import annotations

import os
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from src.assets.paths import AssetPaths  # noqa: E402
from src.data.repository import DataRepository  # noqa: E402

OUTPUT = ROOT / "缺图清单.md"


def collect_usage(data: DataRepository) -> dict[tuple[str, str], list[str]]:
    """portrait → 出现的场景（按场景顺序去重）。"""
    usage: dict[tuple[str, str], list[str]] = OrderedDict()
    for scene_id in data.scene_order:
        scene = data.scene(scene_id)
        for command in scene.timeline:
            if command.get("cmd") != "dialogue":
                continue
            try:
                block = data.dialogue_block(str(command.get("block", "")))
            except Exception:
                continue
            for line in block.lines:
                if not line.portrait or line.is_narration:
                    continue
                key = (line.speaker, line.portrait)
                scenes = usage.setdefault(key, [])
                if scene_id not in scenes:
                    scenes.append(scene_id)
    return usage


def main() -> int:
    data = DataRepository(AssetPaths(ROOT)).load()
    usage = collect_usage(data)
    missing = {(item.get("character"), item["id"]) for item in data.missing_assets()
               if item["kind"] == "paper_doll"}

    lines: list[str] = []
    lines.append("# 缺图清单（第二轮交付）")
    lines.append("")
    lines.append("> 自动生成：`python tools/gen_missing_report.py`；数据来源 `python -m src --check-assets`。")
    lines.append("> 现阶段所有缺失项都走**占位纸片**（角色代表色圆角矩形 + 名字），流程不崩。")
    lines.append("")

    # --- 纸片 ---
    lines.append("## 1. 角色纸片（现实世界阶段立绘）")
    lines.append("")
    lines.append("规格：透明背景 PNG，画布 720 × 1080，人物高 900px、脚底对齐画布底部；放到对应目录即自动替换占位。")
    lines.append("")
    total = 0
    for char_id in ("anon", "tomori", "soyo", "taki", "rana"):
        character = data.character(char_id)
        items = [(portrait, scenes) for (cid, portrait), scenes in usage.items() if cid == char_id]
        if not items:
            continue
        status = "官方" if character.color_status == "official" else "占位色（待定）"
        hex_color = "#%02X%02X%02X" % character.color
        lines.append(f"### {character.name}（`{char_id}`，代表色 `{hex_color}`，{status}）")
        lines.append("")
        lines.append("| 立绘文件 | 出现的 Scene | 状态 |")
        lines.append("|---|---|---|")
        for portrait, scenes in items:
            state = "缺" if (char_id, portrait) in missing else "已有"
            if state == "缺":
                total += 1
            lines.append(f"| `assets/characters/paper_dolls/{char_id}/{portrait}.png` | "
                         f"{'、'.join(s.upper() for s in scenes)} | {state} |")
        lines.append("")
    lines.append(f"小计：缺 {total} 张纸片。")
    lines.append("")

    # --- 背景 ---
    lines.append("## 2. 场景背景")
    lines.append("")
    lines.append("| 文件 | 用途 | 状态 |")
    lines.append("|---|---|---|")
    for item in data.required_assets():
        if item["kind"] != "background":
            continue
        state = "缺" if not Path(item["path"]).is_file() else "已有"
        lines.append(f"| `{Path(item['path']).relative_to(ROOT).as_posix()}` | {item['label']} | {state} |")
    lines.append("")
    lines.append("> `s05_cabin.png`（客轮内舱）视觉稿里没有，当前的图是**程序化占位背景**，"
                 "需要一张正式的船舱内景替换。")
    lines.append("")

    # --- 音频 ---
    lines.append("## 3. 音频")
    lines.append("")
    lines.append("剧情文档要求的 BGM 一条都没有，当前 `music` 指令全部安静跳过（不报错）：")
    lines.append("")
    lines.append("| 音乐 ID | 文件 | 用在哪 |")
    lines.append("|---|---|---|")
    scenes_by_music: dict[str, list[str]] = {}
    for scene_id in data.scene_order:
        scene = data.scene(scene_id)
        if scene.music:
            scenes_by_music.setdefault(scene.music, []).append(scene_id)
    music_specs = data.config.value("audio", "music", default={}) or {}
    for music_id, spec in music_specs.items():
        scenes = scenes_by_music.get(music_id, [])
        lines.append(f"| `{music_id}` | `assets/audio/{spec.get('file', '')}` | "
                     f"{'、'.join(s.upper() for s in scenes) if scenes else '—'} |")
    lines.append("")
    lines.append("音效与环境音目前用**程序化合成**（正弦/方波 + 滤波噪声），不占素材配额；"
                 "正式音效到位后在 `data/config.json` 的 `audio.sfx` / `audio.ambience` 里替换即可。")
    lines.append("")

    # --- 字体 ---
    lines.append("## 4. 字体")
    lines.append("")
    pixel_fonts = sorted((ROOT / "assets" / "fonts").glob("*fusion-pixel*zh_hans*.ttf")) + \
        sorted((ROOT / "assets" / "fonts").glob("zpix.ttf"))
    galgame_fonts = sorted((ROOT / "assets" / "fonts").glob("SourceHanSans*.otf")) + \
        sorted((ROOT / "assets" / "fonts").glob("NotoSansSC*.otf"))
    pixel_state = f"已有 `{pixel_fonts[0].name}`（Fusion Pixel，OFL-1.1）" if pixel_fonts else "**缺**"
    galgame_state = f"已有 `{galgame_fonts[0].name}`（思源黑体，OFL-1.1）" if galgame_fonts \
        else "**缺**"
    lines.append("| 用途 | 期望 | 现状 |")
    lines.append("|---|---|---|")
    lines.append(f"| 像素段落（HUD / 菜单 / 标题） | Zpix 或 Fusion Pixel 12/24px | {pixel_state} |")
    lines.append(f"| 现实段落（对话正文） | 思源黑体 Regular/Medium | {galgame_state} |")
    lines.append("")
    lines.append("> Zpix 是付费商用授权，故按《整体风格与UI》第 6 节选用并列允许的 "
                 "Fusion Pixel（`python tools/fetch_fonts.py` 可重新下载）。")
    lines.append("")
    lines.append("补法：把字体文件放进 `assets/fonts/`，"
                 "在 `data/config.json` 的 `fonts.candidates` 里把路径排到最前即可，无需改代码。")
    lines.append("")

    lines.append("## 5. 其它待补")
    lines.append("")
    lines.append("- 千早爱音等五人的像素 Sprite：当前是 `src/art/pixel_doll.py` 程序化生成的占位帧"
                 "（倒地 / 呼吸 / 坐起 / 站立 / 行走 2 帧），需要正式 32×64 像素图替换。")
    lines.append("- 樱花花瓣 / 雨丝 / 雾团 / 浪花已用数据驱动粒子实现（`src/ui/particles.py`），"
                 "如需更精细的手绘序列帧可替换。")
    lines.append("")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写出 {OUTPUT.relative_to(ROOT)}（纸片缺口 {total} 张）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
