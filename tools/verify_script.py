"""校验游戏台词与《第一轮剧情.md》逐句一致。

做法：
1. 从剧情文档里按出现顺序抽出所有「……」引号台词。
2. 按 scenes.json 的 timeline 顺序，收集实际会被播放的文本：
   - dialogue 台词段里的 text
   - chat 群聊消息的 text
   - subtitle 广播字幕的 text
3. 逐条比对顺序与内容，报告缺失、多余、顺序错位。

用法：python tools/verify_script.py  （退出码 0 = 一致）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLOT = ROOT / "提示词工程部分" / "操作提示词" / "epoch提示词" / "第一轮剧情.md"
DATA = ROOT / "data"

QUOTE = re.compile(r"「([^」]*)」")


def doc_lines() -> list[str]:
    text = PLOT.read_text(encoding="utf-8")
    # 只取「二、正式剧情」到「三、场景连续性」之间的台词
    start = text.find("# 二、正式剧情")
    end = text.find("# 三、场景连续性")
    body = text[start:end] if start >= 0 and end > start else text
    return [m.group(1).strip() for m in QUOTE.finditer(body)]


def game_lines() -> list[tuple[str, str]]:
    scenes = json.loads((DATA / "scenes.json").read_text(encoding="utf-8"))
    dialogues = json.loads((DATA / "dialogues.json").read_text(encoding="utf-8"))["blocks"]
    result: list[tuple[str, str]] = []
    for scene_id in scenes["order"]:
        scene = scenes["scenes"][scene_id]
        for command in scene["timeline"]:
            cmd = command.get("cmd")
            if cmd == "dialogue":
                block = dialogues.get(command["block"])
                if block is None:
                    result.append((scene_id, f"<缺失台词段 {command['block']}>"))
                    continue
                for line in block["lines"]:
                    result.append((scene_id, line.get("text", "").strip()))
            elif cmd == "chat":
                for message in command.get("messages", []):
                    result.append((scene_id, str(message.get("text", "")).strip()))
            elif cmd == "subtitle":
                result.append((scene_id, str(command.get("text", "")).strip()))
    return result


def normalise(text: str) -> str:
    return text.replace("「", "").replace("」", "").replace(" ", "").replace("　", "").strip()


def main() -> int:
    expected = [normalise(item) for item in doc_lines()]
    actual_raw = game_lines()
    actual = [normalise(text) for _, text in actual_raw]

    print(f"剧情文档台词 {len(expected)} 句；游戏内实际播放 {len(actual)} 句")

    problems: list[str] = []
    index = 0
    for position, line in enumerate(expected):
        if index < len(actual) and actual[index] == line:
            index += 1
            continue
        # 尝试在后面找（说明中间多了别的句子）
        try:
            found = actual.index(line, index)
        except ValueError:
            problems.append(f"第 {position + 1} 句在游戏里找不到：{line}")
            continue
        for extra in range(index, found):
            scene_id = actual_raw[extra][0]
            problems.append(f"游戏里多出文档没有的台词（{scene_id}）：{actual[extra]}")
        index = found + 1

    for leftover in actual_raw[index:]:
        problems.append(f"游戏里多出文档没有的台词（{leftover[0]}）：{leftover[1]}")

    if problems:
        print(f"\n发现 {len(problems)} 处不一致：")
        for item in problems:
            print("  -", item)
        return 1

    print("全部一致：顺序与内容均与剧情文档相同。")
    print("按场景统计：")
    counts: dict[str, int] = {}
    for scene_id, _ in actual_raw:
        counts[scene_id] = counts.get(scene_id, 0) + 1
    for scene_id in sorted(counts):
        print(f"  {scene_id}: {counts[scene_id]} 句")
    return 0


if __name__ == "__main__":
    sys.exit(main())
