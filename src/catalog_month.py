# -*- coding: utf-8 -*-
"""カタログJSONから対象年月(YYYYMM)だけを標準出力に書く。CI から使う。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jartic_opendata_kisei_dl import resolve_catalog, year_month  # noqa: E402

print(year_month(resolve_catalog()["entry"]))
