# -*- coding: utf-8 -*-
"""dataset.json の組み立てのテスト。

ビューワが読む配信URLをここで決めているので、
「サイズで同梱/R2 を切り替える」「R2 なら月次キーを指す」を押さえる。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402
import dataset as ds  # noqa: E402

REPORT = {
    "rows_total": 100,
    "features_total": 90,
    "by_layer": {"stop": {"label": "一時停止", "n": 90}},
    "by_prefecture": {"01": {"stop": 90}},
    "anomalies": {"座標なし": 5, "形態不一致": 5},
}
TILES = {
    "min_zoom": 9,
    "max_zoom": 14,
    "max_tile_bytes": 0,
    "n_layers": 13,
    "tippecanoe_version": "2.80.0",
}


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pmtiles = Path(self.tmp.name) / "regulation.pmtiles"
        self.pmtiles.write_bytes(b"x" * 1024)
        self.limit = config.REPO_FILE_LIMIT_MB

    def tearDown(self):
        config.REPO_FILE_LIMIT_MB = self.limit
        self.tmp.cleanup()

    def build(self):
        return ds.build("202607", "2026年07月", "2026年09月01日", REPORT, TILES, self.pmtiles)

    def test_小さければリポジトリ同梱になる(self):
        d = self.build()
        self.assertTrue(d["pmtiles_in_repo"])
        self.assertEqual(d["pmtiles_url"], "data/regulation.pmtiles")
        self.assertNotIn("pmtiles_latest_url", d)

    def test_上限を超えたらR2の月次キーを指す(self):
        config.REPO_FILE_LIMIT_MB = 0
        d = self.build()
        self.assertFalse(d["pmtiles_in_repo"])
        self.assertEqual(d["pmtiles_url"], config.month_url("202607"))
        self.assertIn("202607", d["pmtiles_url"])
        # latest は dataset.json を読まない利用者向けの別口
        self.assertEqual(d["pmtiles_latest_url"], config.latest_url())
        self.assertNotEqual(d["pmtiles_url"], d["pmtiles_latest_url"])

    def test_サイズとハッシュを記録する(self):
        d = self.build()
        self.assertEqual(d["pmtiles_bytes"], 1024)
        self.assertEqual(d["pmtiles_sha256"], hashlib.sha256(b"x" * 1024).hexdigest())

    def test_パース結果を要約する(self):
        d = self.build()
        self.assertEqual(d["rows_total"], 100)
        self.assertEqual(d["features_total"], 90)
        self.assertEqual(d["anomalies_total"], 10)
        self.assertEqual(d["prefectures"], ["01"])
        self.assertEqual(d["n_prefectures"], 1)

    def test_タイル生成の事実を残す(self):
        d = self.build()
        self.assertEqual(d["tiles"]["min_zoom"], 9)
        self.assertEqual(d["tiles"]["max_zoom"], 14)
        self.assertEqual(d["tiles"]["tippecanoe_version"], "2.80.0")

    def test_書き出して読み戻せる(self):
        path = Path(self.tmp.name) / "dataset.json"
        d = self.build()
        ds.save(d, path)
        self.assertEqual(ds.load(path), d)
        self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))

    def test_無いファイルは空辞書になる(self):
        self.assertEqual(ds.load(Path(self.tmp.name) / "なし.json"), {})


class TestPublishedDataset(unittest.TestCase):
    """リポジトリに入っている dataset.json 自体の整合。"""

    def setUp(self):
        self.d = json.loads(config.DATASET.read_text(encoding="utf-8"))

    def test_ビューワが読むURLがある(self):
        self.assertTrue(self.d.get("pmtiles_url"))

    def test_同梱でなければ絶対URLを指す(self):
        if not self.d["pmtiles_in_repo"]:
            self.assertTrue(self.d["pmtiles_url"].startswith("https://"))

    def test_年月の形式(self):
        self.assertRegex(self.d["year_month"], r"^\d{6}$")


if __name__ == "__main__":
    unittest.main()
