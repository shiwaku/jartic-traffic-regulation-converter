# -*- coding: utf-8 -*-
"""行区切りGeoJSON から PMTiles を1本作る。

レイヤーは規制の用途ごとに分ける(tippecanoe -L)。
生成パラメータ(ズーム域・タイルサイズ上限)と tippecanoe のピン留め版は
data/pipeline.json が情報源。何で作ったかは tiles_report.json に残す。

使い方:
  python3 src/build_tiles.py --work work --out work/regulation.pmtiles
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

# 注意: tippecanoe の -L(名前付きレイヤー)は per-layer の minzoom を受け付けない。
# 点レイヤー(一時停止など)の低ズームでの密度は --drop-densest-as-needed に任せる。


def tippecanoe_version() -> str:
    """`tippecanoe v2.80.0` → `2.80.0`。取れなければ空文字。"""
    try:
        out = subprocess.run(
            ["tippecanoe", "--version"], capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    m = re.search(r"v?(\d+\.\d+\.\d+)", (out.stdout or "") + (out.stderr or ""))
    return m.group(1) if m else ""


def require_tippecanoe() -> str:
    """tippecanoe の在処とバージョンを確かめる。無ければここで止める。"""
    if not shutil.which("tippecanoe"):
        raise SystemExit(
            "tippecanoe が見つからない。\n"
            "  Windows には配布が無いので WSL2 側で実行する:\n"
            "    wsl.exe -- bash -lc 'cd <リポジトリ> && python3 src/run_pipeline.py run'\n"
            "  導入: https://github.com/felt/tippecanoe"
        )
    ver = tippecanoe_version()
    if ver and ver != config.TIPPECANOE_VERSION:
        print(
            f"警告: tippecanoe {ver} で作る(data/pipeline.json のピン留めは "
            f"{config.TIPPECANOE_VERSION})。生成物が CI と一致しない可能性がある。",
            file=sys.stderr,
        )
    return ver


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--work", default=str(config.work_dir()))
    p.add_argument("--out", default=None, help="既定は <work>/" + config.PMTILES_NAME)
    p.add_argument("--report", default=None, help="既定は <work>/tiles_report.json")
    args = p.parse_args()

    version = require_tippecanoe()
    work = Path(args.work)
    out = Path(args.out) if args.out else work / config.PMTILES_NAME
    report = Path(args.report) if args.report else work / "tiles_report.json"

    cmd = [
        "tippecanoe", "-o", str(out), "--force",
        f"-Z{config.MIN_ZOOM}", f"-z{config.MAX_ZOOM}", "-r1",
        "--drop-densest-as-needed", "--extend-zooms-if-still-dropping",
        "-P",
    ]
    # 0 は無制限。上限を付けると密な都心のタイルが間引かれるが、
    # 巨大タイルはモバイルの描画とメモリを直撃する。どちらを取るかは設定で決める。
    if config.MAX_TILE_BYTES:
        cmd += ["--maximum-tile-bytes", str(config.MAX_TILE_BYTES)]
    else:
        cmd += ["--no-tile-size-limit"]
    # CI ではプログレス表示が数MBのログになるので黙らせる。
    if os.environ.get("GITHUB_ACTIONS") == "true":
        cmd += ["-q"]

    n = 0
    for name in config.layers():
        f = work / f"regulation_{name}.geojsonl"
        if not f.exists():
            continue
        cmd += ["-L", json.dumps({"file": str(f), "layer": name}, ensure_ascii=False)]
        n += 1
    if not n:
        raise SystemExit(f"{work} に regulation_*.geojsonl がありません")

    print(
        f"tippecanoe {version or '?'} -Z{config.MIN_ZOOM} -z{config.MAX_ZOOM} "
        f"maximum-tile-bytes={config.MAX_TILE_BYTES or '無制限'} (-L × {n})",
        file=sys.stderr,
    )
    subprocess.run(cmd, check=True)

    size = out.stat().st_size
    report.write_text(
        json.dumps(
            {
                "pmtiles_bytes": size,
                "min_zoom": config.MIN_ZOOM,
                "max_zoom": config.MAX_ZOOM,
                "max_tile_bytes": config.MAX_TILE_BYTES,
                "n_layers": n,
                "tippecanoe_version": version,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"完了: {out}  {size / 1e6:.1f}MB / {n}レイヤー", file=sys.stderr)


if __name__ == "__main__":
    main()
