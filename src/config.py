# -*- coding: utf-8 -*-
"""パイプライン共通の設定とパス。

設定値の単一の情報源は data/ の JSON で、Python・ビューワ(TypeScript)・
GitHub Actions のどれもそこを読む。ここは Python 側の読み口。

  data/pipeline.json          配信先・ズーム域・サイズ閾値・tippecanoe バージョン
  data/attributes.json        タイルに載せる属性(元CSV列名・キー・表示名)
  data/regulation_layers.json 規制種別コード → 表示レイヤー

中間生成物の置き場所は環境変数 JARTIC_WORK_DIR で動かせる。
WSL2 から /mnt/c 上のリポジトリを触ると work も drvfs 上になり、数GBの
中間ファイルの読み書きが桁で遅くなるため、ext4 側を指すのに使う。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data"

DATASET = DATA / "dataset.json"
PARSE_REPORT = DATA / "parse_report.json"
PIPELINE_JSON = DATA / "pipeline.json"
ATTRIBUTES_JSON = DATA / "attributes.json"
LAYERS_JSON = DATA / "regulation_layers.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


_cfg = _load(PIPELINE_JSON)

TIPPECANOE_VERSION: str = _cfg["tippecanoe_version"]

_tiles = _cfg["tiles"]
MIN_ZOOM: int = _tiles["min_zoom"]
MAX_ZOOM: int = _tiles["max_zoom"]
DISPLAY_MIN_ZOOM: int = _tiles["display_min_zoom"]
MAX_TILE_BYTES: int = _tiles["max_tile_bytes"]  # 0 = 無制限

REPO_FILE_LIMIT_MB: int = _cfg["repo_file_limit_mb"]
PMTILES_NAME: str = _cfg["pmtiles_name"]

R2: dict = _cfg["r2"]
R2_BUCKET: str = R2["bucket"]
R2_PREFIX: str = R2["prefix"]
R2_PUBLIC_BASE: str = R2["public_base"]
R2_KEEP_MONTHS: int = R2["keep_months"]


def work_dir() -> Path:
    """中間生成物の置き場所。既定は <リポジトリ>/work。"""
    env = os.environ.get("JARTIC_WORK_DIR")
    return Path(env).expanduser().resolve() if env else ROOT / "work"


def attributes() -> list[dict]:
    """タイルに載せる属性。並び順がポップアップの表示順。"""
    return _load(ATTRIBUTES_JSON)["attributes"]


def layers() -> dict:
    """レイヤー名 → {label, codes, color}。"""
    return _load(LAYERS_JSON)["layers"]


# ---- R2 のキー設計 --------------------------------------------------------
# 月次キーは一度書いたら動かさない(ビューワが読む)。latest は毎月上書きする。
# PMTiles は1ファイルを Range で細切れに読むため、差し替え中のキーを読ませると
# 新旧のバイト列をまたいで取得してタイルが壊れる。月次キーはその事故が起きない。

def month_key(year_month: str) -> str:
    return f"{R2_PREFIX}/{year_month}/{PMTILES_NAME}"


def latest_key() -> str:
    return f"{R2_PREFIX}/{PMTILES_NAME}"


def month_url(year_month: str) -> str:
    return f"{R2_PUBLIC_BASE}/{year_month}/{PMTILES_NAME}"


def latest_url() -> str:
    return f"{R2_PUBLIC_BASE}/{PMTILES_NAME}"


def in_repo_url() -> str:
    """リポジトリ同梱のときビューワが読む相対パス。"""
    return f"data/{PMTILES_NAME}"
