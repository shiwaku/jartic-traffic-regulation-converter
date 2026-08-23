# -*- coding: utf-8 -*-
"""取得 → パース → タイル生成 → 品質ゲート → data/ 反映 を1コマンドで通す。

  python3 src/run_pipeline.py doctor  # 実行できる環境か先に確かめる
  python3 src/run_pipeline.py check   # 新しい月が出ているかだけ見る
  python3 src/run_pipeline.py run     # 取得から data/ 反映まで通す

終了コード: 0 正常 / 10 新しい月がある(check) / 20 品質ゲートで止めた / 30 環境不備

tippecanoe は Windows 向けの配布が無いので、手元では WSL2 の中で実行する。
中間生成物は数GBになるため、置き場所は環境変数 JARTIC_WORK_DIR で ext4 側へ
逃がせる(/mnt/c 上に置くと drvfs 越しの読み書きで桁で遅くなる)。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_tiles  # noqa: E402
import ci  # noqa: E402
import config  # noqa: E402
import dataset as ds  # noqa: E402
import gate  # noqa: E402

# 全国分の目安: zip 320MB + 中間GeoJSONL 約1.6GB + PMTiles 約0.6GB。
# 途中で溢れると数十分ぶんが無駄になるので、余裕を見て先に確かめる。
NEEDED_GB = 8

WSL_HINT = (
    "tippecanoe が PATH に無い。Windows 向けの配布が無いので WSL2 の中で実行する:\n"
    "      wsl.exe bash -lc "
    '"cd /mnt/c/.../jartic-traffic-regulation-converter && '
    'JARTIC_WORK_DIR=~/jartic-work python3 src/run_pipeline.py run"'
)


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True, cwd=config.ROOT)


def catalog_month() -> tuple[str, str, str]:
    sys.path.insert(0, str(config.SRC))
    from jartic_opendata_kisei_dl import resolve_catalog, year_month

    entry = resolve_catalog()["entry"]
    return year_month(entry), entry.get("targetMonth", ""), entry.get("releaseDay", "")


# ---- 環境チェック ----------------------------------------------------------

def preflight(work: Path) -> list[str]:
    """走らせる前に分かる不備を並べて返す。空なら通す。

    タイル生成は最後の段なので、ここで見ないと「320MB 落としてパースまで
    終えてから tippecanoe が無くて落ちる」ことになる。
    """
    problems: list[str] = []

    if not shutil.which("tippecanoe"):
        problems.append(WSL_HINT)
    else:
        ver = build_tiles.tippecanoe_version()
        if ver and ver != config.TIPPECANOE_VERSION:
            print(
                f"注意: tippecanoe {ver}(data/pipeline.json のピン留めは "
                f"{config.TIPPECANOE_VERSION})",
                file=sys.stderr,
            )

    try:
        work.mkdir(parents=True, exist_ok=True)
        free_gb = shutil.disk_usage(work).free / 1e9
        if free_gb < NEEDED_GB:
            problems.append(
                f"{work} の空きが {free_gb:.1f}GB。全国分には {NEEDED_GB}GB ほど要る"
            )
    except OSError as e:
        problems.append(f"work ディレクトリを作れない: {work} ({e})")

    for p in (config.PIPELINE_JSON, config.ATTRIBUTES_JSON, config.LAYERS_JSON):
        if not p.exists():
            problems.append(f"設定ファイルが無い: {p}")

    return problems


def cmd_doctor() -> int:
    work = config.work_dir()
    print(f"リポジトリ : {config.ROOT}")
    print(f"work       : {work}")
    print(f"python     : {sys.version.split()[0]}")
    print(
        f"tippecanoe : {build_tiles.tippecanoe_version() or '(無し)'} "
        f"(ピン留め {config.TIPPECANOE_VERSION})"
    )
    print(
        f"タイル     : Z{config.MIN_ZOOM}-Z{config.MAX_ZOOM} / "
        f"表示は Z{config.DISPLAY_MIN_ZOOM} から / "
        f"タイル上限 {config.MAX_TILE_BYTES or '無制限'}"
    )
    print(f"属性       : {len(config.attributes())}件 / レイヤー {len(config.layers())}種")
    problems = preflight(work)
    if problems:
        print("\n不備:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 30
    print("\n実行できる")
    return 0


# ---- 新しい月の有無 --------------------------------------------------------

def cmd_check() -> int:
    ym, month, release = catalog_month()
    prev = ds.load()
    print(f"カタログ: {month} (公開 {release}) / year_month={ym}")
    print(
        f"手元    : {prev.get('target_month', '(なし)')} / "
        f"year_month={prev.get('year_month', '-')}"
    )
    has_new = prev.get("year_month") != ym
    print("新しい月がある" if has_new else "更新なし")
    # CI はこの出力だけで判断する(カタログを二度取りに行かない)。
    ci.emit(has_new=str(has_new).lower(), year_month=ym, release_day=release)
    return 10 if has_new else 0


# ---- 本体 ------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    work = config.work_dir()
    problems = preflight(work)
    if problems:
        print("環境が整っていない:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        ci.emit(gate="skipped", reason="preflight")
        return 30

    ym, month, release = catalog_month()
    catalog = work / "zip" / "catalog.json"
    if args.skip_download and not catalog.exists():
        raise SystemExit(f"--skip-download を指定したが {catalog} が無い")

    # 取得だけは CI が別ステップで済ませている(生zipの退避を品質ゲートより
    # 先にやるため)。--skip-download はその1段だけを飛ばす。
    # --reuse は手元での試行用に、成果物がある段を全部飛ばす。
    steps = [
        (catalog, args.skip_download,
         [sys.executable, "src/jartic_opendata_kisei_dl.py", "--out", str(work / "zip")]),
        (work / "parse_report.json", False,
         [sys.executable, "src/parse_regulation.py",
          "--zip-dir", str(work / "zip"), "--out", str(work)]),
        (work / config.PMTILES_NAME, False,
         [sys.executable, "src/build_tiles.py", "--work", str(work)]),
    ]
    for artifact, always_skip, cmd in steps:
        if always_skip or (args.reuse and artifact.exists()):
            print(f"skip {artifact}", file=sys.stderr)
            continue
        run(cmd)

    report = json.loads((work / "parse_report.json").read_text(encoding="utf-8"))
    tiles_report = work / "tiles_report.json"
    tiles = json.loads(tiles_report.read_text(encoding="utf-8")) if tiles_report.exists() else {}
    pmtiles = work / config.PMTILES_NAME

    new = ds.build(ym, month, release, report, tiles, pmtiles)

    prev = ds.load()
    fails = gate.check(new, prev, args.max_feature_drop)
    if fails and not args.force:
        print("\n品質ゲートに落ちた:", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        print("data/ は書き換えていない。--force で上書きできる。", file=sys.stderr)
        ci.emit(gate="fail", year_month=ym, violations="; ".join(fails))
        ci.summary(
            f"## 品質ゲートで止めた（{month}）\n\n" + "\n".join(f"- {f}" for f in fails)
        )
        return 20

    config.DATA.mkdir(exist_ok=True)
    shutil.copy2(work / "parse_report.json", config.PARSE_REPORT)
    ds.save(new)
    if new["pmtiles_in_repo"]:
        shutil.copy2(pmtiles, config.DATA / config.PMTILES_NAME)
        print(f"data/{config.PMTILES_NAME} を更新した ({new['pmtiles_mb']}MB)", file=sys.stderr)
    else:
        print(
            f"PMTiles が {new['pmtiles_mb']}MB でリポジトリ上限"
            f"({config.REPO_FILE_LIMIT_MB}MB)を超えた。R2 へ配布する:\n"
            f"  {new['pmtiles_url']}  (月次・不変。ビューワが読む)\n"
            f"  {new['pmtiles_latest_url']}  (latest)\n"
            f"  $ python3 src/publish_r2.py",
            file=sys.stderr,
        )
    run([sys.executable, "src/update_docs.py"])
    print("完了", file=sys.stderr)
    ci.emit(
        gate="pass",
        year_month=ym,
        pmtiles_in_repo=str(new["pmtiles_in_repo"]).lower(),
        pmtiles_mb=str(new["pmtiles_mb"]),
    )
    ci.summary(
        f"## {month} を反映した\n\n"
        f"- フィーチャ {new['features_total']:,} / レコード {new['rows_total']:,}\n"
        f"- 都道府県 {new['n_prefectures']}/47\n"
        f"- PMTiles {new['pmtiles_mb']}MB "
        f"({'リポジトリ同梱' if new['pmtiles_in_repo'] else 'R2 配信'})\n"
    )
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="実行できる環境か確かめる")
    sub.add_parser("check", help="新しい月が出ているかだけ見る")
    r = sub.add_parser("run", help="取得から data/ 反映まで通す")
    r.add_argument("--max-feature-drop", type=float, default=gate.DEFAULT_MAX_FEATURE_DROP,
                   help="前回比のフィーチャ数減少の許容割合(既定 5%%)")
    r.add_argument("--force", action="store_true", help="品質ゲートを無視して反映する")
    r.add_argument("--reuse", action="store_true",
                   help="work/ に成果物があれば取得・パース・タイル生成を飛ばす")
    r.add_argument("--skip-download", action="store_true",
                   help="取得済みの work/zip を使う(取得だけを飛ばす。CI 用)")
    args = p.parse_args()
    if args.cmd == "doctor":
        sys.exit(cmd_doctor())
    if args.cmd == "check":
        sys.exit(cmd_check())
    sys.exit(cmd_run(args))


if __name__ == "__main__":
    main()
