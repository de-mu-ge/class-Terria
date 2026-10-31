"""命令行入口解析。

python -m src                              正常启动
python -m src --scene 03                   只跑 Scene 03（含后续）
python -m src --check-assets               列出缺失素材（缺图清单）
python -m src --headless --autoplay --speed 8 --capture out/  自动跑通并截图
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app import Application, AppOptions
from .assets.paths import AssetPaths
from .core.logging_utils import setup_logging
from .data.repository import DataError, DataRepository, normalize_scene_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src", description="直到再次相遇 · 序章")
    parser.add_argument("--scene", help="只启动指定 Scene（01/1/s01 均可）")
    parser.add_argument("--headless", action="store_true", help="无窗口模式（SDL dummy）")
    parser.add_argument("--autoplay", action="store_true", help="自动推进对话（验证用）")
    parser.add_argument("--speed", type=float, default=1.0, help="时间倍率，默认 1.0")
    parser.add_argument("--capture", dest="capture_dir", help="截图输出目录")
    parser.add_argument("--capture-times", dest="capture_times", default="",
                        help="截图时间点（秒，逗号分隔）")
    parser.add_argument("--debug", action="store_true", help="显示调试信息")
    parser.add_argument("--no-audio", action="store_true", help="禁用音频")
    parser.add_argument("--window-scale", type=int, default=None, help="窗口整数倍缩放，默认取配置")
    parser.add_argument("--max-seconds", type=float, default=600.0, help="最长运行时间")
    parser.add_argument("--check-assets", action="store_true", help="检查并列出缺失素材")
    parser.add_argument("--list-scenes", action="store_true", help="列出所有场景")
    parser.add_argument("--smoke", action="store_true",
                        help="自检：从开始界面自动进入 Scene 01，并自动推进到生存模式占位画面")
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    root = Path(__file__).resolve().parent.parent
    try:
        data = DataRepository(AssetPaths(root)).load()
    except DataError as exc:
        print(f"[数据错误] {exc}", file=sys.stderr)
        return 2

    if args.list_scenes:
        for scene_id in data.scene_order:
            scene = data.scene(scene_id)
            print(f"{scene.index:02d}  {scene.id}  {scene.title}  "
                  f"[{scene.stage}/{scene.pipeline}]  {len(scene.timeline)} 指令")
        return 0

    if args.check_assets:
        required = data.required_assets()
        missing = data.missing_assets()
        print(f"应有素材 {len(required)} 项，缺失 {len(missing)} 项")
        for item in missing:
            kind = {"background": "背景", "paper_doll": "纸片"}.get(item["kind"], item["kind"])
            print(f"  [{kind}] {item['label']}  →  {item['path']}")
        fonts = data.config.value("fonts", "candidates", default={})
        print("字体候选：")
        for family, paths in fonts.items():
            existing = [p for p in paths if Path(p).is_file() or (root / p).is_file()]
            print(f"  {family}: {'；'.join(existing) if existing else '（全部缺失，将退回默认字体）'}")
        return 0

    capture_times = []
    if args.capture_times:
        for chunk in args.capture_times.split(","):
            chunk = chunk.strip()
            if chunk:
                capture_times.append(float(chunk))

    scene = normalize_scene_id(args.scene) if args.scene else None
    autoplay = args.autoplay or args.smoke
    options = AppOptions(
        scene=scene,
        headless=args.headless,
        autoplay=autoplay,
        speed=args.speed,
        capture_dir=args.capture_dir,
        capture_times=sorted(capture_times),
        debug=args.debug,
        no_audio=args.no_audio,
        window_scale=args.window_scale,
        max_seconds=args.max_seconds,
        quit_on_handoff=autoplay and args.headless,
        smoke=args.smoke,
    )
    try:
        app = Application(options, project_root=root)
    except DataError as exc:
        print(f"[数据错误] {exc}", file=sys.stderr)
        return 2
    return app.run()
