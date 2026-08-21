# -*- coding: utf-8 -*-
"""data/dataset.json と parse_report.json から README の各節を生成する。

対象年月・件数はここを単一の情報源とし、README とビューワの表示を揃える。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "dataset.json"
REPORT = ROOT / "data" / "parse_report.json"
README = ROOT / "README.md"
BEGIN, END = "<!-- dataset:begin -->", "<!-- dataset:end -->"
LBEGIN, LEND = "<!-- layers:begin -->", "<!-- layers:end -->"
ABEGIN, AEND = "<!-- availability:begin -->", "<!-- availability:end -->"


def replace_block(text: str, begin: str, end: str, body: str) -> str:
    pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    return pat.sub(f"{begin}\n{body}\n{end}", text)


def build_dataset_table(d: dict) -> str:
    dist = "リポジトリ同梱" if d.get("pmtiles_in_repo") else "Release アセット(Range配信)"
    return "\n".join([
        "| 項目 | 内容 |",
        "|---|---|",
        f"| 対象年月 | {d['target_month']} |",
        f"| 公開日 | {d['release_day']}(JARTIC) |",
        f"| 都道府県 | {d['n_prefectures']}／47 |",
        f"| レコード数 | {d['rows_total']:,}件 |",
        f"| 地図に載るフィーチャ数 | {d['features_total']:,}件 |",
        f"| 形状異常 | {d['anomalies_total']:,}件（data/parse_report.json に内訳） |",
        f"| PMTiles | {d['pmtiles_mb']}MB（{dist}） |",
    ])


def build_layer_table(d: dict) -> str:
    rows = ["| レイヤー | 件数 |", "|---|---|"]
    for _, v in sorted(d.get("by_layer", {}).items(), key=lambda kv: -kv[1]["n"]):
        rows.append(f"| {v['label']} | {v['n']:,} |")
    return "\n".join(rows)


def build_availability() -> str:
    """種別ごとの提供都道府県数。47未満のものだけ並べる。

    JARTIC は都道府県警察ごとに提供情報の差が大きい。
    「全国データ」と思って使うと、ある県には1件も無い種別に気づかない。
    """
    if not REPORT.exists():
        return ""
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    avail = rep.get("code_availability", {})
    if not avail:
        return ""
    best: dict[str, tuple[str, int]] = {}
    for key, n in rep.get("by_kind", {}).items():
        code, name = key.split("|", 1)
        if code not in best or n > best[code][1]:
            best[code] = (name, n)
    rows = []
    for code, prefs in avail.items():
        if len(prefs) >= 47:
            continue
        name, n = best.get(code, ("", 0))
        rows.append((len(prefs), -n, code, name, n))
    if not rows:
        return ""
    rows.sort()
    out = ["| コード | 種別（代表名称） | 提供都道府県 | 全国件数 |", "|---|---|---|---|"]
    for n_pref, _, code, name, n in rows:
        out.append(f"| {code} | {name} | {n_pref}／47 | {n:,} |")
    return "\n".join(out)


def main() -> None:
    d = json.loads(DATASET.read_text(encoding="utf-8"))
    text = README.read_text(encoding="utf-8")
    text = replace_block(text, BEGIN, END, build_dataset_table(d))
    text = replace_block(text, LBEGIN, LEND, build_layer_table(d))
    avail = build_availability()
    if avail:
        text = replace_block(text, ABEGIN, AEND, avail)
    README.write_text(text, encoding="utf-8")
    print(f"README を更新した ({d['target_month']})")


if __name__ == "__main__":
    main()
