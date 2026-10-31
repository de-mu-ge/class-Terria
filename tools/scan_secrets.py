"""推送前安全检查：扫描已跟踪文件里的密钥 / 预签名 URL 痕迹。

背景：视觉生图脚本曾把带 `X-Tos-Credential=AKLT...` 的预签名 URL 写进 manifest.json，
被 GitHub push protection 拦下。本脚本用于在推送前自查。

用法：
    python tools/scan_secrets.py          # 扫描 git 已跟踪文件
    python tools/scan_secrets.py --path . # 扫描整个工作区（含未跟踪）

退出码：0 = 干净，1 = 发现可疑内容。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 只匹配“凭证痕迹”，不匹配正常文本
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("火山方舟 AK ID", re.compile(r"AKLT[A-Za-z0-9]{8,}")),
    ("预签名 URL 凭证", re.compile(r"X-Tos-Credential")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("Bearer 头", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}")),
    ("api_key 赋值", re.compile(r"api[_-]?key\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.I)),
]

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc", ".xcf", ".ttf", ".ttc", ".otf", ".wav", ".ogg"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    )
    names = [n for n in result.stdout.decode("utf-8", "replace").split("\0") if n]
    return [ROOT / name for name in names]


def workspace_files() -> list[Path]:
    return [
        p for p in ROOT.rglob("*")
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
    ]


def scan(files: list[Path]) -> list[tuple[Path, int, str, str]]:
    hits: list[tuple[Path, int, str, str]] = []
    for path in files:
        if path.suffix.lower() in SKIP_SUFFIX or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if match:
                    raw = match.group(0)
                    masked = raw[:4] + "***" + f"(len={len(raw)})"
                    hits.append((path, lineno, label, masked))
                    break
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="推送前密钥自查")
    parser.add_argument("--path", help="扫描整个工作区而不是仅 git 跟踪文件")
    args = parser.parse_args()

    files = workspace_files() if args.path else tracked_files()
    hits = scan(files)
    print(f"扫描 {len(files)} 个文件，命中 {len(hits)} 处")
    for path, lineno, label, masked in hits:
        rel = path.relative_to(ROOT).as_posix()
        print(f"  [{label}] {rel}:{lineno}  {masked}")
    if hits:
        print("\n存在可疑凭证，先清洗再推送。")
        return 1
    print("干净。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
