# -*- coding: utf-8 -*-
"""PMTiles を Cloudflare R2 へ公開する。

  python3 src/publish_r2.py                 # data/dataset.json の年月で公開する
  python3 src/publish_r2.py --dry-run       # 何をするかだけ出す
  python3 src/publish_r2.py --copy-latest   # 手元に PMTiles が無いとき、
                                            # R2 上の latest を月次キーへ複製する

置くキーは2本。

  {prefix}/{年月}/regulation.pmtiles  月次・不変。**ビューワが読むのはこちら**
  {prefix}/regulation.pmtiles         latest。毎月上書きする

PMTiles は1ファイルを Range リクエストで細切れに読む。latest をビューワに
読ませると、月次の差し替えと再生が重なったときに新旧のバイト列をまたいで取得し、
タイルが壊れる。月次キーは一度書いたら動かさないので、その事故が起きない。
latest は dataset.json を読まない利用者向けの口として置く。

書き込みは月次キー → latest の順。それぞれアップロード後にサイズを検証し、
月次キーが検証に通らなければ latest には触らない(公開中のビューワは前月の
月次キーを読み続けるので、中途半端な状態にならない)。

古い月次キーは data/pipeline.json の r2.keep_months より前を削除する。
残っている月は data/history.json に書き出す(バケットの実際の状態から作る)。

必要な環境変数: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY と、
R2_ENDPOINT もしくは R2_ACCOUNT_ID。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import dataset as ds  # noqa: E402

HISTORY = config.DATA / "history.json"

MONTH_CACHE = "public, max-age=31536000, immutable"
LATEST_CACHE = "public, max-age=300, must-revalidate"


def endpoint() -> str:
    ep = os.environ.get("R2_ENDPOINT")
    if ep:
        return ep
    account = os.environ.get("R2_ACCOUNT_ID")
    if not account:
        raise SystemExit("R2_ENDPOINT か R2_ACCOUNT_ID が要る")
    return f"https://{account}.r2.cloudflarestorage.com"


def aws(args: list[str], capture: bool = False) -> str:
    cmd = ["aws", *args, "--endpoint-url", endpoint()]
    print("$ " + " ".join(cmd[:6]) + " ...", file=sys.stderr)
    r = subprocess.run(cmd, check=True, text=True,
                       capture_output=capture)
    return (r.stdout or "").strip() if capture else ""


def remote_size(key: str) -> int:
    out = aws(["s3api", "head-object", "--bucket", config.R2_BUCKET, "--key", key,
               "--query", "ContentLength", "--output", "text"], capture=True)
    return int(out)


def put(path: Path, key: str, cache: str, expect: int, dry: bool) -> None:
    """アップロードして、置けたサイズを確かめる。合わなければ止める。"""
    if dry:
        print(f"[dry-run] put {key}  ({expect:,} bytes, {cache})")
        return
    aws(["s3", "cp", str(path), f"s3://{config.R2_BUCKET}/{key}",
         "--content-type", "application/octet-stream", "--cache-control", cache])
    got = remote_size(key)
    if got != expect:
        raise SystemExit(f"アップロード後のサイズが合わない: {key} ({got} != {expect})")
    print(f"公開: {key}  ({got:,} bytes)")


def copy_latest_to_month(ym: str, dry: bool) -> int:
    """R2 上の latest を月次キーへ複製する(サーバ側コピー。転送は発生しない)。

    月次キーの運用を始める前に公開した月を、あとから月次キーに置くための口。
    latest は毎月上書きされるので、その月のうちにしか使えない。
    """
    key = config.month_key(ym)
    size = remote_size(config.latest_key())
    if dry:
        print(f"[dry-run] copy {config.latest_key()} -> {key} ({size:,} bytes)")
        return size
    # `aws s3 cp` のバケット間コピーは GetObjectTagging を呼ぶが、R2 はこれを
    # 実装していない(NotImplemented)。タグを触らない copy-object を使う。
    # メタデータは引き継がずここで付け直す(--metadata-directive REPLACE)。
    aws(["s3api", "copy-object",
         "--bucket", config.R2_BUCKET, "--key", key,
         "--copy-source", f"{config.R2_BUCKET}/{config.latest_key()}",
         "--metadata-directive", "REPLACE",
         "--content-type", "application/octet-stream",
         "--cache-control", MONTH_CACHE], capture=True)
    got = remote_size(key)
    if got != size:
        raise SystemExit(f"複製後のサイズが合わない: {key} ({got} != {size})")
    print(f"複製: {key} ({got:,} bytes)")
    return got


def month_keys() -> list[str]:
    """バケットにある月次キーを新しい順に返す。"""
    out = aws(["s3api", "list-objects-v2", "--bucket", config.R2_BUCKET,
               "--prefix", f"{config.R2_PREFIX}/", "--query", "Contents[].Key",
               "--output", "json"], capture=True)
    keys = json.loads(out) if out and out != "None" else []
    pat = re.compile(
        rf"^{re.escape(config.R2_PREFIX)}/(\d{{6}})/{re.escape(config.PMTILES_NAME)}$"
    )
    return sorted((k for k in (keys or []) if pat.match(k)), reverse=True)


def prune(keep_current: str, dry: bool) -> list[str]:
    """keep_months より古い月次キーを消し、残った月を新しい順で返す。"""
    try:
        keys = month_keys()
    except (subprocess.CalledProcessError, OSError) as e:
        if not dry:
            raise
        print(f"[dry-run] 一覧が取れないので剪定は省略 ({e})", file=sys.stderr)
        return [keep_current]
    months = [re.search(r"/(\d{6})/", k).group(1) for k in keys]
    keep = months[: config.R2_KEEP_MONTHS]
    for key, ym in zip(keys, months):
        if ym in keep or ym == keep_current:
            continue
        if dry:
            print(f"[dry-run] delete {key}")
            continue
        aws(["s3api", "delete-object", "--bucket", config.R2_BUCKET, "--key", key])
        print(f"削除: {key}")
    return [m for m in months if m in keep or m == keep_current]


def write_history(months: list[str], dry: bool) -> None:
    """R2 に残っている月を data/history.json に書く。過去月の入口の一覧。"""
    if dry:
        print(f"[dry-run] data/history.json ({len(months)}か月)")
        return
    HISTORY.write_text(
        json.dumps(
            {
                "_comment": "R2 に残っている月次キー(新しい順)。"
                "src/publish_r2.py がバケットの実際の状態から書く。",
                "keep_months": config.R2_KEEP_MONTHS,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "latest_url": config.latest_url(),
                "months": [
                    {"year_month": m, "url": config.month_url(m)} for m in months
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"data/history.json を更新した ({len(months)}か月)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pmtiles", default=None,
                   help="既定は <work>/" + config.PMTILES_NAME)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--copy-latest", action="store_true",
                   help="手元の PMTiles を使わず、R2 上の latest を月次キーへ複製する")
    args = p.parse_args()

    d = ds.load()
    if not d:
        raise SystemExit("data/dataset.json が無い。先に run_pipeline.py run を通す。")
    if d.get("pmtiles_in_repo"):
        print(f"PMTiles は {d['pmtiles_mb']}MB でリポジトリ同梱。R2 へは上げない。")
        return

    ym = d["year_month"]

    if args.copy_latest:
        copy_latest_to_month(ym, args.dry_run)
        months = prune(ym, args.dry_run)
        write_history(months, args.dry_run)
        print(
            "月次キーを用意した。dataset.json の pmtiles_url を月次キーに向けるには\n"
            f"  {config.month_url(ym)}\n"
            "を書く(次回の run_pipeline.py run では自動でこうなる)。"
        )
        return

    pmtiles = Path(args.pmtiles) if args.pmtiles else config.work_dir() / config.PMTILES_NAME
    if not pmtiles.exists():
        raise SystemExit(f"{pmtiles} が無い")

    size = pmtiles.stat().st_size
    # dataset.json の値と食い違うファイルを上げると、ビューワが読む URL と
    # 中身が一致しなくなる。ここで気づく。
    if d.get("pmtiles_bytes") and d["pmtiles_bytes"] != size:
        raise SystemExit(
            f"{pmtiles} のサイズが dataset.json と違う "
            f"({size:,} != {d['pmtiles_bytes']:,})。作り直したものを上げていないか確認する。"
        )

    # ビューワが読む URL と、いま上げるキーが一致していることを確かめる。
    # ここがずれると「dataset.json は在るはずのキーを指しているのに404」になる。
    want = config.month_url(ym)
    if d.get("pmtiles_url") != want:
        print(
            f"注意: dataset.json の pmtiles_url が月次キーを指していない。\n"
            f"  いま: {d.get('pmtiles_url')}\n"
            f"  想定: {want}",
            file=sys.stderr,
        )

    put(pmtiles, config.month_key(ym), MONTH_CACHE, size, args.dry_run)
    put(pmtiles, config.latest_key(), LATEST_CACHE, size, args.dry_run)

    months = prune(ym, args.dry_run)
    write_history(months, args.dry_run)


if __name__ == "__main__":
    main()
