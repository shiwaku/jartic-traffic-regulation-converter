# -*- coding: utf-8 -*-
"""data/dataset.json の生成と読み書き。

このファイルが、公開されたデータについての単一の情報源になる。
README(src/update_docs.py)もビューワも、対象年月・件数・PMTiles の配信URLを
ここから読む。配布先を変えてもビューワのコードは触らない。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import config


def load(path: Path | None = None) -> dict:
    p = path or config.DATASET
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(d: dict, path: Path | None = None) -> None:
    p = path or config.DATASET
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(ym: str, month: str, release: str, report: dict, tiles: dict, pmtiles: Path) -> dict:
    """パース結果とタイル生成結果から dataset.json の内容を組む。"""
    size = pmtiles.stat().st_size
    in_repo = size / 1e6 <= config.REPO_FILE_LIMIT_MB

    d = {
        "target_month": month,
        "release_day": release,
        "year_month": ym,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows_total": report.get("rows_total", 0),
        "features_total": report.get("features_total", 0),
        "by_layer": report.get("by_layer", {}),
        "prefectures": sorted(report.get("by_prefecture", {}).keys()),
        "n_prefectures": len(report.get("by_prefecture", {})),
        "anomalies_total": sum(report.get("anomalies", {}).values()),
        "pmtiles_mb": round(size / 1e6, 1),
        "pmtiles_bytes": size,
        # 配布先で検証できるようにする。CI のアップロード後検証もこの値を使う。
        "pmtiles_sha256": sha256(pmtiles),
        "pmtiles_in_repo": in_repo,
        # ビューワが読む URL。R2 のときは上書きされない月次キーを指す。
        # latest を読ませると、差し替え中に新旧のバイト列をまたいだ Range 取得が
        # 起きてタイルが壊れる。
        "pmtiles_url": config.in_repo_url() if in_repo else config.month_url(ym),
        # 実際に収録されたズーム域と、それを作った tippecanoe。
        # 設定(data/pipeline.json)ではなく「この配信物の事実」を記録する。
        "tiles": {
            "min_zoom": tiles.get("min_zoom"),
            "max_zoom": tiles.get("max_zoom"),
            "max_tile_bytes": tiles.get("max_tile_bytes"),
            "n_layers": tiles.get("n_layers"),
            "tippecanoe_version": tiles.get("tippecanoe_version"),
        },
    }
    if not in_repo:
        # dataset.json を読まない利用者向けの「常に最新」の口。
        d["pmtiles_latest_url"] = config.latest_url()
    return d
