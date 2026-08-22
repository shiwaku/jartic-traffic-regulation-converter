# -*- coding: utf-8 -*-
"""合成zipで parse_regulation.py を端から端まで通す。

実データは 320MB あるので CI では回せない。代わりに「実データで踏んだ罠」を
数十行に詰めた zip を作って、同じ経路(zipをストリーム読み → GeoJSONL +
parse_report.json)を通す。tippecanoe は要らない。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import config  # noqa: E402
import parse_regulation as pr  # noqa: E402

GEOM_COL = pr.COL_GEOM


def csv_text() -> str:
    """実データと同じ「全項目ダブルクォート囲み」のCSVを組む。

    列は「属性表に載っているもの」＋「パースに必須のもの」。
    """
    cols = [a["source"] for a in config.attributes() if "source" in a]
    cols += [c for c in pr.REQUIRED_COLS if c not in cols]
    idx = {c: i for i, c in enumerate(cols)}

    def row(code: str, shape: str, coords: str, pref: str = "01", **kw) -> str:
        v = [""] * len(cols)
        v[idx[pr.COL_CODE]] = code
        v[idx[pr.COL_SHAPE]] = shape
        v[idx[pr.COL_PREF]] = pref
        v[idx["県別規制種別名称"]] = kw.get("kind", "テスト規制")
        v[idx[GEOM_COL]] = coords
        return ",".join(f'"{x}"' for x in v)

    long_line = ";".join(f"{141.0 + i * 1e-5:.6f} 43.0" for i in range(20000))
    rows = [
        ",".join(f'"{c}"' for c in cols),
        # 1. 一時停止(63)・点コード・1点 → Point
        row("63", "1", "141.35 43.06", kind="一時停止"),
        # 2. 一方通行(11)・線コード・3点 → LineString
        row("11", "2", "141.35 43.06;141.36 43.06;141.37 43.07", kind="一方通行"),
        # 3. 立入禁止部分(19)・面コード・3点 → Polygon(閉じる)
        row("19", "3", "141.35 43.06;141.36 43.06;141.36 43.07"),
        # 4. 形態不一致(点コードなのに2点)
        row("63", "1", "141.35 43.06;141.36 43.07"),
        # 5. 座標なし → 出力しない
        row("63", "1", ""),
        # 6. 未知コード → other レイヤー
        row("99999", "1", "141.35 43.06"),
        # 7. csv の既定上限(128KB)を超える座標フィールド
        row("63", "2", long_line),
        # 8. 日本の範囲外の座標が混じる(元データ由来の誤り)
        row("63", "1", "0 0;141.35 43.06;200 43"),
        # 9. 別の都道府県。提供種別の差を数えられること
        row("98", "1", "139.76 35.68", pref="13", kind="信号機"),
    ]
    return "\r\n".join(rows) + "\r\n"


class TestEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        work = Path(cls.tmp.name)
        zip_dir = work / "zip"
        zip_dir.mkdir()
        # zip 内のファイル名は日本語(実データもそう)。cp932 のCSVを入れる。
        with zipfile.ZipFile(zip_dir / "typeD_test.zip", "w") as z:
            z.writestr("交通規制情報.csv", csv_text().encode("cp932"))

        r = subprocess.run(
            [sys.executable, "src/parse_regulation.py",
             "--zip-dir", str(zip_dir), "--out", str(work)],
            cwd=ROOT, capture_output=True, text=True,
        )
        cls.proc = r
        cls.work = work
        report = work / "parse_report.json"
        cls.report = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def features(self, layer: str) -> list[dict]:
        f = self.work / f"regulation_{layer}.geojsonl"
        if not f.exists():
            return []
        return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines()]

    def test_正常終了する(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_全行を数える(self):
        self.assertEqual(self.report["rows_total"], 9)

    def test_座標なしの行は出力しない(self):
        self.assertEqual(self.report["features_total"], 8)
        self.assertEqual(self.report["anomalies"]["座標なし"], 1)

    def test_列欠落を報告しない(self):
        # 属性表のすべての列を持つCSVを作っているので、欠落は出ないはず
        self.assertFalse([k for k in self.report["anomalies"] if k.startswith("列欠落")])

    def test_点線面のジオメトリを作る(self):
        self.assertEqual(self.features("stop")[0]["geometry"]["type"], "Point")
        self.assertEqual(self.features("oneway")[0]["geometry"]["type"], "LineString")
        poly = self.features("no_entry")[0]["geometry"]
        self.assertEqual(poly["type"], "Polygon")
        self.assertEqual(poly["coordinates"][0][0], poly["coordinates"][0][-1])

    def test_形態不一致を数える(self):
        self.assertEqual(self.report["anomalies"]["形態不一致"], 1)
        self.assertEqual(self.report["shape_mismatch_detail"], {"形態1→2点": 1})

    def test_未知コードはotherに落ちる(self):
        self.assertEqual(len(self.features("other")), 1)
        self.assertEqual(self.features("other")[0]["properties"]["code"], "99999")

    def test_128KB超の座標フィールドを読める(self):
        longest = max(
            (len(f["geometry"]["coordinates"]) for f in self.features("stop")),
            default=0,
        )
        self.assertEqual(longest, 20000)

    def test_範囲外座標を落として数える(self):
        self.assertEqual(self.report["broken_coordinate_points"], 2)

    def test_タイルに載る属性は属性表のキーだけ(self):
        allowed = {a["key"] for a in config.attributes()}
        for f in self.features("stop"):
            self.assertLessEqual(set(f["properties"]), allowed)

    def test_uidは載せない(self):
        # 実測でタイルの48%を占めていたため外した(data/attributes.json)
        for f in self.features("stop"):
            self.assertNotIn("uid", f["properties"])

    def test_都道府県ごとの提供種別を数える(self):
        avail = self.report["code_availability"]
        self.assertEqual(avail["98"], ["13"])
        self.assertEqual(avail["63"], ["01"])
        self.assertEqual(sorted(self.report["by_prefecture"]), ["01", "13"])

    def test_0件レイヤーのファイルは残さない(self):
        # tippecanoe が空ファイルで落ちるため消している
        self.assertFalse((self.work / "regulation_bicycle.geojsonl").exists())
        self.assertNotIn("bicycle", self.report["by_layer"])


class TestMemberName(unittest.TestCase):
    """zip 内のファイル名が cp932 で格納されている場合(実データにある)。"""

    def test_UTF8フラグがあればそのまま使う(self):
        info = zipfile.ZipInfo("交通規制情報.csv")
        info.flag_bits |= 0x800
        self.assertEqual(pr.member_name(info), "交通規制情報.csv")

    def test_フラグが無ければcp932として読む(self):
        raw = "交通規制情報.csv".encode("cp932")
        info = zipfile.ZipInfo(raw.decode("cp437"))
        info.flag_bits = 0
        self.assertEqual(pr.member_name(info), "交通規制情報.csv")

    def test_cp932として読めなければそのまま返す(self):
        info = zipfile.ZipInfo("plain.csv")
        info.flag_bits = 0
        self.assertEqual(pr.member_name(info), "plain.csv")


if __name__ == "__main__":
    unittest.main()
