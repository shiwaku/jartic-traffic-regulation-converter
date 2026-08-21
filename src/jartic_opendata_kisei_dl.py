# -*- coding: utf-8 -*-
"""JARTIC「交通規制情報」(typeD) を47都道府県分ダウンロードする。

配布URLは月次で変わる(`.../opendata/{更新日時}/typeD_{都道府県ローマ字}.zip`)ため、
更新日時や対象年月はスクリプトに埋め込まず公式のカタログJSONから解決する。

**JARTIC は最新1か月分しか配布しない。** 過去月のURLは404になるので、
生zipは公開ウィンドウ内に取得する必要がある。

使い方:
  python3 src/jartic_opendata_kisei_dl.py --out work/zip
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CATALOG_URL = "https://www.jartic.or.jp/d/opendata/opendata.json"
BASE_URL = "https://www.jartic.or.jp/d/opendata"
TARGET_TYPE = "typeD"
UA = {"User-Agent": "jartic-traffic-regulation-converter/0.1"}
RETRIES = 3


def fetch(url: str, timeout: int = 300) -> bytes:
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
    raise SystemExit(f"取得できなかった: {url} ({last})")


def resolve_catalog() -> dict:
    """カタログから typeD のエントリを取り出す。"""
    catalog = json.loads(fetch(CATALOG_URL, timeout=60).decode("utf-8"))
    entry = next((e for e in catalog if e.get("type") == TARGET_TYPE), None)
    if not entry:
        raise SystemExit(f"カタログに {TARGET_TYPE} が無い")
    return {"catalog": catalog, "entry": entry}


def year_month(entry: dict) -> str:
    """"2026年06月" → "202606"。"""
    return re.sub(r"[^0-9]", "", entry.get("targetMonth", ""))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="work/zip")
    p.add_argument("--only", nargs="*", help="カタログID(R01 等)を指定して絞る")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    resolved = resolve_catalog()
    entry = resolved["entry"]
    ym = year_month(entry)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    targets = entry.get("targetList", [])
    if args.only:
        wanted = set(args.only)
        targets = [t for t in targets if t.get("id") in wanted]
    if not targets:
        raise SystemExit("対象が0件")

    # カタログのスナップショットを残す。配布URLが消えたあとに何を取ったか辿れるようにする。
    (out / "catalog.json").write_text(
        json.dumps(
            {"target_month": entry.get("targetMonth"),
             "release_day": entry.get("releaseDay"),
             "year_month": ym,
             "targets": targets,
             "full_catalog": resolved["catalog"]},
            ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"対象年月 {entry.get('targetMonth')} / 公開日 {entry.get('releaseDay')} / {len(targets)}ファイル",
          file=sys.stderr)
    total = 0
    for i, t in enumerate(targets, 1):
        name = t["link"].split("/")[-1]
        dest = out / name
        if dest.exists() and not args.force:
            print(f"[{i}/{len(targets)}] cached  {name}", flush=True)
            total += dest.stat().st_size
            continue
        url = BASE_URL + t["link"]
        data = fetch(url)
        dest.write_bytes(data)
        total += len(data)
        print(f"[{i}/{len(targets)}] {len(data) / 1e6:7.1f}MB  {name}", flush=True)
    print(f"完了: {out} に {len(targets)}ファイル / 計 {total / 1e6:.0f}MB", file=sys.stderr)


if __name__ == "__main__":
    main()
