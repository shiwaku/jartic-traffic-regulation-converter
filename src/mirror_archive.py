# -*- coding: utf-8 -*-
"""生zipと成果物を月ごとのローカルアーカイブへ取り込む。

**JARTIC は最新1か月分しか配布しない。** 過去月の配布URLは消えるため、
生データは公開ウィンドウ内に確保しないと復旧できない。
CI では `raw-YYYYMM` の Release へ退避し、ここではそれを手元へ引く。

  python3 src/mirror_archive.py                 # Release から取り込む
  python3 src/mirror_archive.py --from-work     # 手元の work/ から取り込む
既定の保存先は ../jartic-archive/{年月}/(環境変数 JARTIC_ARCHIVE_DIR で変更)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

ROOT = config.ROOT
DEFAULT_DIR = ROOT.parent / "jartic-archive"
ARTIFACTS = ["parse_report.json", "dataset.json"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def year_month() -> str:
    ds = config.DATASET
    if ds.exists():
        return json.loads(ds.read_text(encoding="utf-8"))["year_month"]
    cat = config.work_dir() / "zip" / "catalog.json"
    if cat.exists():
        return json.loads(cat.read_text(encoding="utf-8"))["year_month"]
    raise SystemExit("年月が分からない。先に run_pipeline を実行する。")


def from_release(ym: str, dest: Path) -> None:
    if not shutil.which("gh"):
        raise SystemExit("gh CLI が無い。--from-work を使うか gh を入れる。")
    tag = f"raw-{ym}"
    print(f"gh release download {tag} → {dest}", file=sys.stderr)
    subprocess.run(
        ["gh", "release", "download", tag, "--dir", str(dest), "--clobber"],
        check=True, cwd=ROOT,
    )


def from_work(dest: Path) -> None:
    work = config.work_dir()
    zips = sorted((work / "zip").glob("typeD_*.zip"))
    if not zips:
        raise SystemExit(f"{work / 'zip'} に typeD_*.zip が無い")
    for z in zips:
        shutil.copy2(z, dest / z.name)
    cat = work / "zip" / "catalog.json"
    if cat.exists():
        shutil.copy2(cat, dest / "catalog.json")
    for name in ARTIFACTS:
        for base in (config.DATA, work):
            p = base / name
            if p.exists():
                shutil.copy2(p, dest / name)
                break


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--from-work", action="store_true")
    p.add_argument("--dir", default=os.environ.get("JARTIC_ARCHIVE_DIR", str(DEFAULT_DIR)))
    args = p.parse_args()

    ym = year_month()
    dest = Path(args.dir) / ym
    dest.mkdir(parents=True, exist_ok=True)

    if args.from_work:
        from_work(dest)
    else:
        from_release(ym, dest)

    manifest = {
        "year_month": ym,
        "files": {
            f.name: {"bytes": f.stat().st_size, "sha256": sha256(f)}
            for f in sorted(dest.iterdir())
            if f.is_file() and f.name != "MANIFEST.json"
        },
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(v["bytes"] for v in manifest["files"].values())
    print(f"{dest} に {len(manifest['files'])}ファイル / {total / 1e6:.0f}MB", file=sys.stderr)


if __name__ == "__main__":
    main()
