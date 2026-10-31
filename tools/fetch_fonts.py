"""下载并安装规范指定的两套字体（都是 OFL 类授权，可入库）。

- 像素段落：Fusion Pixel 12px monospaced（TakWolf，SIL OFL 1.1）
  规范《整体风格与UI》第 6 节允许 Zpix 或 Fusion Pixel；Zpix 是付费商用授权，故用 Fusion Pixel。
- 现实段落：思源黑体 Source Han Sans CN Regular（Adobe，SIL OFL 1.1）

只抽取需要的单个字重/语言，不保留 48MB 的发布包。

用法：python tools/fetch_fonts.py
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
UA = {"User-Agent": "Mozilla/5.0"}

SOURCE_HAN = {
    "otf": "https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/SubsetOTF/CN/SourceHanSansCN-Regular.otf",
    "license": "https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/LICENSE.txt",
    "license_name": "LICENSE-source-han-sans.txt",
    "out": "SourceHanSansCN-Regular.otf",
}

FUSION_REPO = "TakWolf/fusion-pixel-font"
FUSION_ASSET_KEYWORD = "fusion-pixel-font-12px-monospaced-ttf-v"
FUSION_WANT = "12px-monospaced-zh_hans.ttf"


def fetch(url: str, timeout: int = 180) -> bytes:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def api(url: str) -> dict:
    request = urllib.request.Request(url, headers={**UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def install_source_han() -> None:
    target = FONTS / SOURCE_HAN["out"]
    if target.is_file():
        print(f"[跳过] 已有 {target.name}")
    else:
        data = fetch(SOURCE_HAN["otf"])
        target.write_bytes(data)
        print(f"[下载] {target.name}  {len(data) / 1024 / 1024:.2f} MB")
    license_path = FONTS / SOURCE_HAN["license_name"]
    if not license_path.is_file():
        license_path.write_bytes(fetch(SOURCE_HAN["license"]))
        print(f"[下载] {license_path.name}")


def install_fusion_pixel() -> None:
    existing = sorted(FONTS.glob("*fusion-pixel*zh_hans*.ttf"))
    if existing:
        print(f"[跳过] 已有 {existing[0].name}")
        return

    release = api(f"https://api.github.com/repos/{FUSION_REPO}/releases/latest")
    asset = next(
        (a for a in release.get("assets", [])
         if FUSION_ASSET_KEYWORD in a["name"] and a["name"].endswith(".zip")),
        None,
    )
    if asset is None:
        raise RuntimeError("没找到 Fusion Pixel 的 ttf 发布包")
    print(f"[下载] {asset['name']}  {asset['size'] / 1024 / 1024:.1f} MB（请稍候）")
    blob = fetch(asset["browser_download_url"], timeout=600)

    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        member = next((n for n in archive.namelist() if n.endswith(FUSION_WANT)), None)
        if member is None:
            names = ", ".join(archive.namelist()[:8])
            raise RuntimeError(f"压缩包里没有 {FUSION_WANT}（前几个：{names}）")
        data = archive.read(member)
    target = FONTS / "fusion-pixel-12px-monospaced-zh_hans.ttf"
    target.write_bytes(data)
    print(f"[解出] {target.name}  {len(data) / 1024 / 1024:.2f} MB")

    license_text = fetch(
        f"https://raw.githubusercontent.com/{FUSION_REPO}/master/LICENSE-OFL"
    ).decode("utf-8", "replace")
    (FONTS / "LICENSE-fusion-pixel-OFL.txt").write_text(license_text, encoding="utf-8")
    print("[下载] LICENSE-fusion-pixel-OFL.txt")


def main() -> int:
    FONTS.mkdir(parents=True, exist_ok=True)
    install_source_han()
    install_fusion_pixel()
    print("\n字体清单：")
    for path in sorted(FONTS.glob("*")):
        print(f"  {path.name:<48} {path.stat().st_size / 1024 / 1024:>6.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
