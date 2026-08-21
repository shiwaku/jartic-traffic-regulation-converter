# -*- coding: utf-8 -*-
"""行区切りGeoJSON から PMTiles を1本作る。

レイヤーは規制の用途ごとに分ける(tippecanoe -L)。
点レイヤー(一時停止・信号機・横断歩道)は密度が高いので低ズームで間引き、
線・面レイヤーは形状を残す。

使い方:
  python3 src/build_tiles.py --work work --out work/regulation.pmtiles
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

MAX_ZOOM = 14
# 注意: tippecanoe の -L(名前付きレイヤー)は per-layer の minzoom を受け付けない。
# 点レイヤー(一時停止63,020件など)の低ズームでの密度は
# --drop-densest-as-needed に任せる。



def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--work", default="work")
    p.add_argument("--out", default="work/regulation.pmtiles")
    p.add_argument("--layers", default="data/regulation_layers.json")
    args = p.parse_args()

    if not shutil.which("tippecanoe"):
        raise SystemExit("tippecanoe が見つからない。https://github.com/felt/tippecanoe")

    layers = json.loads(Path(args.layers).read_text(encoding="utf-8"))["layers"]
    work = Path(args.work)
    cmd = [
        "tippecanoe", "-o", args.out, "--force",
        "-Z0", f"-z{MAX_ZOOM}", "-r1",
        "--drop-densest-as-needed", "--extend-zooms-if-still-dropping",
        "--no-tile-size-limit", "-P",
    ]
    n = 0
    for name in layers:
        f = work / f"regulation_{name}.geojsonl"
        if not f.exists():
            continue
        cmd += ["-L", json.dumps({"file": str(f), "layer": name}, ensure_ascii=False)]
        n += 1
    if not n:
        raise SystemExit(f"{work} に regulation_*.geojsonl がありません")

    print(" ".join(cmd[:12]) + f" ... (-L × {n})", file=sys.stderr)
    subprocess.run(cmd, check=True)
    size = Path(args.out).stat().st_size / 1e6
    print(f"完了: {args.out}  {size:.1f}MB / {n}レイヤー", file=sys.stderr)


if __name__ == "__main__":
    main()
