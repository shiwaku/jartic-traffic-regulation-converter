# -*- coding: utf-8 -*-
"""生zipを raw-YYYYMM の GitHub Release へ退避する。

  python3 src/archive_raw.py --zip-dir work/zip

**JARTIC は最新1か月分しか配布しない。** 過去月の配布URLは消えるので、
生データは公開ウィンドウ内に確保しないと復旧できない。だから退避は
**品質ゲートより先に**やる。ゲートに落ちても生データは残る。

年月は取得時に作られた catalog.json から読む(カタログを二度取りに行かない)。
必要なもの: gh CLI と GH_TOKEN。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

NOTES = (
    "JARTIC 交通規制情報の生zip。"
    "JARTIC は最新1か月分しか配布しないため退避したもの。"
)


def gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("$ gh " + " ".join(args), file=sys.stderr)
    return subprocess.run(["gh", *args], check=check, cwd=config.ROOT)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip-dir", default=None, help="既定は <work>/zip")
    args = p.parse_args()

    if not shutil.which("gh"):
        raise SystemExit("gh CLI が無い")

    zip_dir = Path(args.zip_dir) if args.zip_dir else config.work_dir() / "zip"
    catalog = zip_dir / "catalog.json"
    if not catalog.exists():
        raise SystemExit(f"{catalog} が無い。先に取得する。")
    ym = json.loads(catalog.read_text(encoding="utf-8"))["year_month"]

    zips = sorted(zip_dir.glob("typeD_*.zip"))
    if not zips:
        raise SystemExit(f"{zip_dir} に typeD_*.zip が無い")

    tag = f"raw-{ym}"
    if gh(["release", "view", tag], check=False).returncode != 0:
        gh(["release", "create", tag, "--title", f"{tag} 生データ", "--notes", NOTES])

    total = sum(z.stat().st_size for z in zips)
    gh(["release", "upload", tag, *[str(z) for z in zips], str(catalog), "--clobber"])
    print(f"{tag} に {len(zips)}ファイル / {total / 1e6:.0f}MB を退避した", file=sys.stderr)


if __name__ == "__main__":
    main()
