# -*- coding: utf-8 -*-
"""取得 → パース → PMTiles生成 を1コマンドで通し、品質ゲートを通ったものだけ data/ に反映する。

人のレビューを挟まずに公開するため、前回の結果と比べて劣化していたら止める。

  python3 src/run_pipeline.py check   新しい月が出ているかだけ見る
  python3 src/run_pipeline.py run     取得から PMTiles 生成まで通す
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DATA = ROOT / "data"
WORK = ROOT / "work"
DATASET = DATA / "dataset.json"

# PMTiles は 100MB を超えるとリポジトリに置けない。超えたら Release 配布に切り替える。
REPO_FILE_LIMIT_MB = 90


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True, cwd=ROOT)


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def catalog_month() -> tuple[str, str, str]:
    sys.path.insert(0, str(SRC))
    from jartic_opendata_kisei_dl import resolve_catalog, year_month

    e = resolve_catalog()["entry"]
    return year_month(e), e.get("targetMonth", ""), e.get("releaseDay", "")


def cmd_check() -> int:
    ym, month, release = catalog_month()
    prev = load_json(DATASET)
    print(f"カタログ: {month} (公開 {release}) / year_month={ym}")
    print(f"手元    : {prev.get('target_month', '(なし)')} / year_month={prev.get('year_month', '-')}")
    if prev.get("year_month") == ym:
        print("更新なし")
        return 0
    print("新しい月がある")
    return 10


def gate(new: dict, prev: dict, max_drop: float) -> list[str]:
    """公開を止める条件。前回が無ければ何も止めない。"""
    fails = []
    if not prev:
        return fails
    if new["year_month"] <= prev.get("year_month", ""):
        fails.append(f"対象年月が前回より新しくない ({new['year_month']} <= {prev.get('year_month')})")
    pn, nn = prev.get("features_total", 0), new["features_total"]
    if pn and nn < pn * (1 - max_drop):
        fails.append(f"フィーチャ数が前回比 {(1 - nn / pn) * 100:.1f}% 減 ({pn:,} → {nn:,})")
    for layer, cur in new["by_layer"].items():
        was = prev.get("by_layer", {}).get(layer, {}).get("n", 0)
        if was and cur["n"] == 0:
            fails.append(f"レイヤー {layer} が0件になった (前回 {was:,})")
    prev_pref = set(prev.get("prefectures", []))
    lost = prev_pref - set(new["prefectures"])
    if lost:
        fails.append(f"都道府県が欠けた: {sorted(lost)}")
    return fails


def cmd_run(args: argparse.Namespace) -> int:
    ym, month, release = catalog_month()
    WORK.mkdir(exist_ok=True)
    steps = [
        (WORK / "zip" / "catalog.json",
         [sys.executable, "src/jartic_opendata_kisei_dl.py", "--out", "work/zip"]),
        (WORK / "parse_report.json",
         [sys.executable, "src/parse_regulation.py", "--zip-dir", "work/zip", "--out", "work"]),
        (WORK / "regulation.pmtiles",
         [sys.executable, "src/build_tiles.py", "--work", "work",
          "--out", "work/regulation.pmtiles"]),
    ]
    for artifact, cmd in steps:
        if args.reuse and artifact.exists():
            print(f"reuse {artifact.relative_to(ROOT)}", file=sys.stderr)
            continue
        run(cmd)

    rep = load_json(WORK / "parse_report.json")
    pmtiles = WORK / "regulation.pmtiles"
    size_mb = round(pmtiles.stat().st_size / 1e6, 1)
    new = {
        "target_month": month,
        "release_day": release,
        "year_month": ym,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows_total": rep.get("rows_total", 0),
        "features_total": rep.get("features_total", 0),
        "by_layer": rep.get("by_layer", {}),
        "prefectures": sorted(rep.get("by_prefecture", {}).keys()),
        "n_prefectures": len(rep.get("by_prefecture", {})),
        "anomalies_total": sum(rep.get("anomalies", {}).values()),
        "pmtiles_mb": size_mb,
        "pmtiles_in_repo": size_mb <= REPO_FILE_LIMIT_MB,
    }

    prev = load_json(DATASET)
    fails = gate(new, prev, args.max_feature_drop)
    if fails and not args.force:
        print("\n品質ゲートに落ちた:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        print("data/ は書き換えていない。--force で上書きできる。", file=sys.stderr)
        return 20

    DATA.mkdir(exist_ok=True)
    shutil.copy2(WORK / "parse_report.json", DATA / "parse_report.json")
    DATASET.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    if new["pmtiles_in_repo"]:
        shutil.copy2(pmtiles, DATA / "regulation.pmtiles")
        print(f"data/regulation.pmtiles を更新した ({size_mb}MB)", file=sys.stderr)
    else:
        print(
            f"PMTiles が {size_mb}MB でリポジトリ上限({REPO_FILE_LIMIT_MB}MB)を超えた。\n"
            f"work/regulation.pmtiles を R2(shi-works) へ配布し、\n"
            f"ビューワは Range リクエストでそれを読む。",
            file=sys.stderr,
        )
    run([sys.executable, "src/update_docs.py"])
    print("完了", file=sys.stderr)
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("--max-feature-drop", type=float, default=0.05,
                   help="前回比のフィーチャ数減少の許容割合(既定 5%%)")
    r.add_argument("--force", action="store_true", help="品質ゲートを無視して反映する")
    r.add_argument("--reuse", action="store_true",
                   help="work/ に成果物があれば取得・パース・タイル生成を飛ばす")
    args = p.parse_args()
    sys.exit(cmd_check() if args.cmd == "check" else cmd_run(args))


if __name__ == "__main__":
    main()
