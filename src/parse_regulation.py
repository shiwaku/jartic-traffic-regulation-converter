# -*- coding: utf-8 -*-
"""交通規制情報(zip)を行区切りGeoJSONに変換し、品質レポートを出す。

zip を展開せずストリーム処理する。1都道府県のCSVは80MB超あり、
全国分を展開すると数GBになるため、読みながらレイヤーごとの
GeoJSONL に書き出す。

## フォーマット(拡張版標準フォーマット k_2.1)

- 1都道府県警察1ファイルのCSV。**全項目ダブルクォート囲み**、cp932
- 170列。仕様書: https://www.jartic.or.jp/d/opendata/typeD_kisei_73_k_2.1.pdf
- 座標は「規制場所の経度緯度」に **`経度 経度;経度 緯度;...`**(点はスペース区切り、
  点と点はセミコロン区切り)で入る。1フィールドに折れ線が丸ごと入る
- 規制形態は「点・線・面コード」= 1:点 / 2:線 / 3:面

**一方通行の向きは頂点順しかない。** 実データで確認したところ、
一方通行(共通規制種別コード11)の「進入方向」「禁止する方向」「指定する方向」は
いずれも空で、方向を示すのは座標列の順序だけだった。
向きを逆に読むと逆走するネットワークができるため、
利用側では OSM の oneway タグなどで検証すること。

使い方:
  python3 src/parse_regulation.py --zip-dir work/zip --out work
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

# タイルに載せる属性は data/attributes.json が情報源(全170列は載せない)。
# ビューワのポップアップも同じファイルを読むので、増減はあちらだけを直す。
_ATTRS = config.attributes()
KEEP_COLS = [(a["source"], a["key"]) for a in _ATTRS if "source" in a]
DERIVED = {a["key"] for a in _ATTRS if a.get("derived")}

SHAPE_NAME = {"1": "point", "2": "line", "3": "area"}

# ジオメトリの決定とレイヤー分けに必ず要る列。属性表(attributes.json)から
# 外してもパースには要るので、そちらとは別に持つ。
COL_GEOM = "規制場所の経度緯度"
COL_CODE = "共通規制種別コード"
COL_SHAPE = "点・線・面コード"
COL_PREF = "都道府県コード"
REQUIRED_COLS = [COL_GEOM, COL_CODE, COL_SHAPE, COL_PREF]

# 「規制場所の経度緯度」は1フィールドに折れ線が丸ごと入る。
# 実データで 128KB(csv の既定上限)を超える県があったため上限を上げる。
# sys.maxsize を渡すと Windows(C long が32bit)では OverflowError になるので、
# 32bit に収まる最大値にする。実データの最長フィールドより桁違いに大きい。
csv.field_size_limit(2 ** 31 - 1)
COORD_PREC = 6  # 1e-6 度 ≒ 0.1m


def member_name(info: zipfile.ZipInfo) -> str:
    """zip 内のファイル名。UTF-8 フラグが無いものは cp932 で格納されている。"""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp932")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def member_names(z: zipfile.ZipFile):
    for info in z.infolist():
        if info.is_dir():
            continue
        name = member_name(info)
        if name.lower().endswith(".csv"):
            yield info, name


def parse_coords(raw: str) -> tuple[list, int]:
    """"lon lat;lon lat" → [[lon, lat], ...]。壊れた点の数も返す。"""
    pts, broken = [], 0
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        f = chunk.split()
        if len(f) != 2:
            broken += 1
            continue
        try:
            lon, lat = float(f[0]), float(f[1])
        except ValueError:
            broken += 1
            continue
        # 日本の範囲から外れる座標は捨てる(元データ由来の誤りが実際にある)
        if not (122.0 <= lon <= 154.0 and 20.0 <= lat <= 46.0):
            broken += 1
            continue
        pts.append([round(lon, COORD_PREC), round(lat, COORD_PREC)])
    return pts, broken


def build_geometry(shape: str, pts: list) -> tuple[dict | None, str]:
    """規制形態と実際の点数からジオメトリを決める。

    形態コードと点数は必ずしも整合しない(実データで不一致を確認)。
    **点数を優先**し、形態コードとの食い違いはレポートに数える。
    """
    n = len(pts)
    if n == 0:
        return None, "座標なし"
    if n == 1:
        return {"type": "Point", "coordinates": pts[0]}, ("整合" if shape == "1" else "形態不一致")
    if shape == "3":
        ring = pts + [pts[0]] if pts[0] != pts[-1] else pts
        if len(ring) < 4:
            return {"type": "LineString", "coordinates": pts}, "面だが点数不足"
        return {"type": "Polygon", "coordinates": [ring]}, "整合"
    return {"type": "LineString", "coordinates": pts}, ("整合" if shape == "2" else "形態不一致")


def layer_of(code: str, layers: dict) -> str:
    for name, spec in layers.items():
        if code in spec["codes"]:
            return name
    return "other"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip-dir", default="work/zip")
    p.add_argument("--out", default="work")
    p.add_argument("--layers", default=str(config.LAYERS_JSON))
    args = p.parse_args()

    layers = json.loads(Path(args.layers).read_text(encoding="utf-8"))["layers"]
    zip_dir, out_dir = Path(args.zip_dir), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    zips = sorted(zip_dir.glob("typeD_*.zip"))
    if not zips:
        raise SystemExit(f"{zip_dir} に typeD_*.zip がありません")

    handles = {
        name: (out_dir / f"regulation_{name}.geojsonl").open("w", encoding="utf-8")
        for name in layers
    }
    per_layer = Counter()
    per_pref = defaultdict(Counter)
    per_kind = Counter()
    # 都道府県ごとに「どの規制種別を提供しているか」。
    # JARTIC は都道府県警察ごとに提供情報の差が大きく、
    # ある県には存在する種別が別の県には1件も無い(実測)。
    pref_codes = defaultdict(Counter)
    shape_mismatch = Counter()
    anomalies = Counter()
    broken_points = 0
    rows_total = 0

    try:
        for i, zp in enumerate(zips, 1):
            rows_file = 0
            with zipfile.ZipFile(zp) as z:
                for info, member in member_names(z):
                    with z.open(info) as f:
                        reader = csv.reader(
                            io.TextIOWrapper(f, encoding="cp932", errors="replace")
                        )
                        head = next(reader, None)
                        if not head:
                            continue
                        ci = {c: k for k, c in enumerate(head)}
                        missing = [c for c, _ in KEEP_COLS if c not in ci]
                        if missing:
                            anomalies[f"列欠落:{member}"] += 1
                        geom_col = ci.get(COL_GEOM)
                        code_col = ci.get(COL_CODE)
                        shape_col = ci.get(COL_SHAPE)
                        pref_col = ci.get(COL_PREF)
                        if geom_col is None or code_col is None:
                            anomalies[f"必須列なし:{member}"] += 1
                            continue
                        for row in reader:
                            rows_total += 1
                            rows_file += 1
                            if len(row) <= geom_col:
                                anomalies["列不足"] += 1
                                continue
                            pts, broken = parse_coords(row[geom_col])
                            broken_points += broken
                            shape = row[shape_col] if shape_col is not None else ""
                            geom, note = build_geometry(shape, pts)
                            if geom is None:
                                anomalies["座標なし"] += 1
                                continue
                            if note != "整合":
                                anomalies[note] += 1
                                if note == "形態不一致":
                                    shape_mismatch[f"形態{shape}→{len(pts)}点"] += 1
                            code = row[code_col]
                            lname = layer_of(code, layers)
                            props = {}
                            for src, dst in KEEP_COLS:
                                k = ci.get(src)
                                if k is None or k >= len(row):
                                    continue
                                v = row[k].strip()
                                if v:
                                    props[dst] = v
                            # 派生属性。attributes.json から外せば載らない。
                            if "layer" in DERIVED:
                                props["layer"] = lname
                            if "shape_name" in DERIVED:
                                props["shape_name"] = SHAPE_NAME.get(shape, shape)
                            handles[lname].write(
                                json.dumps(
                                    {"type": "Feature", "geometry": geom, "properties": props},
                                    ensure_ascii=False,
                                )
                                + "\n"
                            )
                            per_layer[lname] += 1
                            per_kind[f"{code}|{props.get('kind', '')}"] += 1
                            if pref_col is not None and pref_col < len(row):
                                per_pref[row[pref_col]][lname] += 1
                                pref_codes[row[pref_col]][code] += 1
            print(f"[{i}/{len(zips)}] {zp.name}  {rows_file:,}行", flush=True)
    finally:
        for h in handles.values():
            h.close()

    # 0件のレイヤーのファイルは消す(tippecanoe が空ファイルで落ちる)
    for name in list(handles):
        f = out_dir / f"regulation_{name}.geojsonl"
        if per_layer[name] == 0 and f.exists():
            f.unlink()

    report = {
        "n_zips": len(zips),
        "rows_total": rows_total,
        "features_total": sum(per_layer.values()),
        "by_layer": {
            k: {"label": layers[k]["label"], "n": per_layer[k]}
            for k in layers
            if per_layer[k]
        },
        "by_prefecture": {k: dict(v) for k, v in sorted(per_pref.items())},
        "by_kind": dict(sorted(per_kind.items(), key=lambda kv: -kv[1])),
        "anomalies": dict(anomalies),
        "shape_mismatch_detail": dict(shape_mismatch),
        "broken_coordinate_points": broken_points,
        # 種別ごとに「提供している都道府県コード」。欠けている県が分かる。
        "code_availability": {
            code: sorted(p for p, c in pref_codes.items() if c.get(code))
            for code in sorted({c for cs in pref_codes.values() for c in cs}, key=lambda x: int(x))
        },
        "by_prefecture_code": {p: dict(c) for p, c in sorted(pref_codes.items())},
    }
    (out_dir / "parse_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"完了: {report['features_total']:,} フィーチャ / {rows_total:,} 行  "
        f"異常 {sum(anomalies.values()):,}",
        file=sys.stderr,
    )
    for k, v in report["by_layer"].items():
        print(f"  {v['label']:<16s} {v['n']:>9,}", file=sys.stderr)


if __name__ == "__main__":
    main()
