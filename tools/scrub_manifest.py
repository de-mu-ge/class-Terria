"""清洗视觉生图 manifest.json 里的预签名 URL。

火山方舟返回的图片地址是带签名的临时 URL，查询串里带访问凭证（含 AK ID）。
这类 URL 一旦入库会被 GitHub 密钥扫描拦下，因此只保留对象地址（协议+主机+路径）。

用法：
    python tools/scrub_manifest.py            # 清洗 视觉稿/ 下所有 manifest.json
    python tools/scrub_manifest.py 路径 ...   # 清洗指定文件
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_GLOB = "提示词工程部分/视觉稿/**/manifest.json"


def scrub_value(url: str) -> str:
    if not isinstance(url, str) or url.startswith("(b64"):
        return url
    return url.split("?", 1)[0]


def scrub_file(path: Path) -> int:
    raw = path.read_text(encoding="utf-8-sig")
    changed = 0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 不是严格 JSON：退化成逐行正则
        lines = []
        for line in raw.splitlines():
            if '"url"' in line and "?" in line:
                head, _, rest = line.partition("http")
                url_part, quote, tail = rest.partition('"')
                if "?" in url_part:
                    url_part = url_part.split("?", 1)[0]
                    changed += 1
                lines.append(head + "http" + url_part + quote + tail)
            else:
                lines.append(line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return changed

    for record in data.get("records", []):
        if isinstance(record.get("url"), str):
            new_url = scrub_value(record["url"])
            if new_url != record["url"]:
                record["url"] = new_url
                changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="清洗 manifest.json 里的预签名 URL")
    parser.add_argument("paths", nargs="*", help="要清洗的文件；留空则扫描 视觉稿/ 下全部 manifest.json")
    args = parser.parse_args()

    targets = [Path(p) for p in args.paths] if args.paths else sorted(ROOT.glob(MANIFEST_GLOB))
    if not targets:
        print("没有找到 manifest.json")
        return 0

    total = 0
    for path in targets:
        if not path.is_file():
            print(f"[跳过] 不存在：{path}")
            continue
        changed = scrub_file(path)
        total += changed
        try:
            rel = path.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(path)
        print(f"[清洗] {rel}: 去掉 {changed} 条 URL 查询串")
    print(f"合计清洗 {total} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
