#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉生图模块 —— 火山方舟 doubao-seedream 封装。

设计目标
--------
1. 只依赖 Python 标准库，任何环境 `python generate_image.py` 即可跑通。
2. 单图 / 批量两种模式，批量走 JSON 清单，便于给一整个场景批量出稿。
3. 密钥不硬编码在逻辑里：命令行 > 环境变量 ARK_API_KEY > 同目录 .ark_key。
4. 每次调用都写 manifest，记录提示词、尺寸、耗时、落地路径，方便回溯与人工敲定。

用法
----
单图：
    python generate_image.py --prompt "雪原中举火把前行的旅人，像素风" --out out.png --size 2K

批量（推荐给场景出稿）：
    python generate_image.py --batch scenes.json --outdir ./稿

    scenes.json 形如：
    [
      {"name": "prologue_01_plaza", "prompt": "……", "size": "2K"},
      {"name": "prologue_07_coast", "prompt": "……", "size": "2K"}
    ]

只校验参数、不真正出图：
    python generate_image.py --batch scenes.json --outdir ./稿 --dry-run
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
DEFAULT_MODEL = "doubao-seedream-5-0-pro-260628"
DEFAULT_SIZE = "2K"
HERE = Path(__file__).resolve().parent
LEDGER = HERE / "ledger.json"
TOTAL_QUOTA = 118  # 账号总图片用量，用完为止
KEY_FILES = (HERE / ".ark_key", HERE / "ark_key.txt")
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def read_ledger() -> dict:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"used": 0, "quota": TOTAL_QUOTA, "runs": []}


def record_usage(names: list[str], outdir: Path) -> dict:
    """失败与 dry-run 不计入用量。"""
    if not names:
        return read_ledger()
    ledger = read_ledger()
    ledger["used"] = int(ledger.get("used", 0)) + len(names)
    ledger.setdefault("quota", TOTAL_QUOTA)
    ledger.setdefault("runs", []).append({
        "time": datetime.now().isoformat(timespec="seconds"),
        "count": len(names),
        "names": names,
        "outdir": str(outdir),
    })
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    remaining = ledger["quota"] - ledger["used"]
    log(f"用量 {ledger['used']}/{ledger['quota']}，剩余 {remaining} 张")
    return ledger


def resolve_key(cli_key: str | None) -> str:
    """按 命令行 > 环境变量 > 密钥文件 的顺序解析 API Key。"""
    if cli_key and cli_key.strip():
        return cli_key.strip()
    for env in ("ARK_API_KEY", "DOUBAO_API_KEY", "VOLC_ARK_API_KEY"):
        value = os.environ.get(env)
        if value and value.strip():
            return value.strip()
    for path in KEY_FILES:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value
    raise SystemExit(
        "缺少 API Key。三种提供方式任选其一：\n"
        "  1) --api-key <key>\n"
        "  2) 设置环境变量 ARK_API_KEY\n"
        f"  3) 写入 {KEY_FILES[0]}（该文件应加入 .gitignore）"
    )


def build_payload(prompt: str, model: str, size: str, watermark: bool,
                  negative_prompt: str | None, seed: int | None) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "response_format": "url",
        "size": size,
        "stream": False,
        "watermark": watermark,
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed
    return payload


# --------------------------------------------------------------------------- #
# 网络
# --------------------------------------------------------------------------- #
def post_json(url: str, payload: dict, api_key: str, timeout: int) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError(f"接口返回不是合法 JSON：{body[:400]}")


def request_image(payload: dict, api_key: str, timeout: int, retries: int = 3) -> str:
    """返回图片 URL；对限流与临时故障做指数退避重试。"""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            result = post_json(ENDPOINT, payload, api_key, timeout)
            images = result.get("data") or []
            if not images:
                raise RuntimeError(f"接口未返回图片数据：{json.dumps(result, ensure_ascii=False)[:400]}")
            first = images[0]
            url = first.get("url")
            if not url:
                # 部分返回可能是 b64_json
                b64 = first.get("b64_json")
                if b64:
                    return "b64:" + b64
                raise RuntimeError(f"返回结构缺少 url：{json.dumps(first, ensure_ascii=False)[:300]}")
            return url
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = RuntimeError(f"HTTP {exc.code}: {body}")
            if exc.code not in RETRYABLE_STATUS or attempt == retries:
                raise last_error
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = RuntimeError(f"网络错误：{exc}")
            if attempt == retries:
                raise last_error
        wait = min(30, 2 ** attempt) + random.uniform(0, 1.5)
        log(f"第 {attempt} 次失败（{last_error}），{wait:.1f}s 后重试")
        time.sleep(wait)
    raise last_error  # pragma: no cover


def sniff_format(raw: bytes) -> str:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return "png"


def download_image(url_or_b64: str, out_path: Path, timeout: int) -> tuple[Path, int]:
    """保存到与真实字节格式一致的扩展名，返回 (实际路径, 字节数)。"""
    if url_or_b64.startswith("b64:"):
        import base64
        raw = base64.b64decode(url_or_b64[4:])
    else:
        with urllib.request.urlopen(url_or_b64, timeout=timeout) as response:
            raw = response.read()
    actual = out_path.with_suffix("." + sniff_format(raw))
    actual.parent.mkdir(parents=True, exist_ok=True)
    actual.write_bytes(raw)
    return actual, len(raw)


# --------------------------------------------------------------------------- #
# 任务
# --------------------------------------------------------------------------- #
def run_job(job: dict, api_key: str, outdir: Path, model: str, default_size: str,
            watermark: bool, negative_prompt: str | None, seed: int | None,
            timeout: int, dry_run: bool) -> dict:
    name = job.get("name") or job.get("id") or f"image_{int(time.time())}"
    prompt = (job.get("prompt") or "").strip()
    if not prompt:
        raise SystemExit(f"任务 {name} 缺少 prompt")

    payload = build_payload(
        prompt=prompt,
        model=job.get("model") or model,
        size=job.get("size") or default_size,
        watermark=bool(job.get("watermark", watermark)),
        negative_prompt=job.get("negative_prompt") or negative_prompt,
        seed=job.get("seed", seed),
    )
    record = {
        "name": name,
        "prompt": prompt,
        "payload": payload,
        "started": datetime.now().isoformat(timespec="seconds"),
        "status": "dry-run" if dry_run else "pending",
    }

    if dry_run:
        log(f"[dry-run] {name} size={payload['size']}")
        record["path"] = None
        return record

    log(f"生成 {name} (size={payload['size']})")
    started = time.time()
    try:
        url = request_image(payload, api_key, timeout)
        out_path = outdir / f"{name}.png"
        out_path, size_bytes = download_image(url, out_path, timeout)
        elapsed = time.time() - started
        record.update({
            "status": "ok",
            # 只记录对象地址，丢掉查询串：预签名 URL 的查询串里带访问凭证（含 AK ID），
            # 一旦入库就会被 GitHub 密钥扫描拦下，禁止写进 manifest。
            "url": "(b64_json)" if url.startswith("b64:") else url.split("?", 1)[0],
            "path": str(out_path),
            "bytes": size_bytes,
            "seconds": round(elapsed, 1),
        })
        log(f"完成 {name} -> {out_path.name} ({size_bytes // 1024} KB, {elapsed:.1f}s)")
    except Exception as exc:  # noqa: BLE001 - 批量时单条失败不应中断整批
        record.update({"status": "failed", "error": str(exc),
                       "seconds": round(time.time() - started, 1)})
        log(f"失败 {name}: {exc}")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="视觉生图模块（火山方舟 doubao-seedream 封装）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("用法\n----\n", 1)[-1],
    )
    parser.add_argument("--prompt", help="单图模式：画面描述")
    parser.add_argument("--batch", help="批量模式：任务清单 JSON 路径")
    parser.add_argument("--out", default="output.png", help="单图模式输出路径")
    parser.add_argument("--outdir", default=".", help="批量模式输出目录")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="尺寸，如 2K / 4K / 2048x1152")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型 ID")
    parser.add_argument("--api-key", default=None, help="API Key（默认读环境变量或 .ark_key）")
    parser.add_argument("--negative-prompt", default=None, help="负向提示词")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，便于复现")
    parser.add_argument("--no-watermark", action="store_true", help="关闭水印（默认开启）")
    parser.add_argument("--timeout", type=int, default=240, help="单次请求超时秒数")
    parser.add_argument("--dry-run", action="store_true", help="只打印载荷，不出图")
    args = parser.parse_args(argv)

    if not args.prompt and not args.batch:
        parser.error("需要 --prompt 或 --batch 之一")

    api_key = "" if args.dry_run else resolve_key(args.api_key)
    watermark = not args.no_watermark

    if args.batch:
        batch_path = Path(args.batch)
        jobs = json.loads(batch_path.read_text(encoding="utf-8"))
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs", [])
        if not isinstance(jobs, list) or not jobs:
            raise SystemExit(f"{batch_path} 未解析出任务列表")
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        records = [
            run_job(job, api_key, outdir, args.model, args.size, watermark,
                    args.negative_prompt, args.seed, args.timeout, args.dry_run)
            for job in jobs
        ]
        if args.dry_run:
            log(f"[dry-run] 共 {len(records)} 条任务，载荷校验通过，未消耗额度")
            return 0
        manifest = outdir / "manifest.json"
        manifest.write_text(
            json.dumps({"generated_at": datetime.now().isoformat(timespec="seconds"),
                        "model": args.model, "records": records},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        ok = sum(1 for r in records if r["status"] == "ok")
        log(f"批量结束：成功 {ok}/{len(records)}，清单 {manifest}")
        record_usage([r["name"] for r in records if r["status"] == "ok"], outdir)
        return 0 if ok == len(records) else 1

    out_path = Path(args.out)
    record = run_job({"name": out_path.stem, "prompt": args.prompt},
                     api_key, out_path.parent, args.model, args.size, watermark,
                     args.negative_prompt, args.seed, args.timeout, args.dry_run)
    if record["status"] not in ("ok", "dry-run"):
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 1
    if record["status"] == "ok":
        record_usage([out_path.stem], out_path.parent)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
