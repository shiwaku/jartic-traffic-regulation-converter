# -*- coding: utf-8 -*-
"""パースの単体テスト。README「フォーマットの罠」に対応する。

- 座標は1フィールドに折れ線が丸ごと入る
- 日本の範囲外の座標が混じる(元データ由来)
- 規制形態コードと実際の点数が一致しないことがある
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config  # noqa: E402
import parse_regulation as pr  # noqa: E402


class TestParseCoords(unittest.TestCase):
    def test_折れ線を読む(self):
        pts, broken = pr.parse_coords("141.0 43.0;141.1 43.1;141.2 43.2")
        self.assertEqual(pts, [[141.0, 43.0], [141.1, 43.1], [141.2, 43.2]])
        self.assertEqual(broken, 0)

    def test_丸め桁は6桁(self):
        pts, _ = pr.parse_coords("141.357539927458 43.057881934149")
        self.assertEqual(pts, [[141.35754, 43.057882]])

    def test_空要素と余分な区切りは無視する(self):
        pts, broken = pr.parse_coords(" ;141.0 43.0; ;")
        self.assertEqual(pts, [[141.0, 43.0]])
        self.assertEqual(broken, 0)

    def test_値が2つでない要素は壊れとして数える(self):
        pts, broken = pr.parse_coords("141.0;141.0 43.0 9")
        self.assertEqual(pts, [])
        self.assertEqual(broken, 2)

    def test_数値でない要素は壊れとして数える(self):
        pts, broken = pr.parse_coords("abc def")
        self.assertEqual((pts, broken), ([], 1))

    def test_日本の範囲外は捨てて数える(self):
        # 元データに実在する誤り。経度122〜154・緯度20〜46の外は落とす。
        pts, broken = pr.parse_coords("0 0;141.0 43.0;200.0 43.0;141.0 60.0")
        self.assertEqual(pts, [[141.0, 43.0]])
        self.assertEqual(broken, 3)

    def test_長い折れ線も読める(self):
        raw = ";".join(f"{141 + i * 1e-5:.6f} 43.0" for i in range(20000))
        self.assertGreater(len(raw), 131072)  # csv の既定上限を超える長さ
        pts, broken = pr.parse_coords(raw)
        self.assertEqual((len(pts), broken), (20000, 0))


class TestBuildGeometry(unittest.TestCase):
    def test_点コードで1点なら点(self):
        geom, note = pr.build_geometry("1", [[141.0, 43.0]])
        self.assertEqual(geom["type"], "Point")
        self.assertEqual(note, "整合")

    def test_線コードで1点なら点にして不一致を数える(self):
        geom, note = pr.build_geometry("2", [[141.0, 43.0]])
        self.assertEqual(geom["type"], "Point")
        self.assertEqual(note, "形態不一致")

    def test_点コードで2点なら線にして不一致を数える(self):
        geom, note = pr.build_geometry("1", [[141.0, 43.0], [141.1, 43.1]])
        self.assertEqual(geom["type"], "LineString")
        self.assertEqual(note, "形態不一致")

    def test_線コードで2点なら線(self):
        geom, note = pr.build_geometry("2", [[141.0, 43.0], [141.1, 43.1]])
        self.assertEqual((geom["type"], note), ("LineString", "整合"))

    def test_面コードは閉じたリングにする(self):
        pts = [[141.0, 43.0], [141.1, 43.0], [141.1, 43.1]]
        geom, note = pr.build_geometry("3", pts)
        self.assertEqual(geom["type"], "Polygon")
        self.assertEqual(geom["coordinates"][0][0], geom["coordinates"][0][-1])
        self.assertEqual(note, "整合")

    def test_すでに閉じている面は点を足さない(self):
        pts = [[141.0, 43.0], [141.1, 43.0], [141.1, 43.1], [141.0, 43.0]]
        geom, _ = pr.build_geometry("3", pts)
        self.assertEqual(len(geom["coordinates"][0]), 4)

    def test_面コードで点数が足りなければ線にする(self):
        geom, note = pr.build_geometry("3", [[141.0, 43.0], [141.1, 43.1]])
        self.assertEqual((geom["type"], note), ("LineString", "面だが点数不足"))

    def test_座標が無ければジオメトリを作らない(self):
        geom, note = pr.build_geometry("1", [])
        self.assertIsNone(geom)
        self.assertEqual(note, "座標なし")


class TestLayerOf(unittest.TestCase):
    def setUp(self):
        self.layers = config.layers()

    def test_一時停止はstop(self):
        self.assertEqual(pr.layer_of("63", self.layers), "stop")

    def test_一方通行はoneway(self):
        self.assertEqual(pr.layer_of("11", self.layers), "oneway")

    def test_未知のコードはotherに落ちる(self):
        self.assertEqual(pr.layer_of("99999", self.layers), "other")

    def test_空文字もotherに落ちる(self):
        self.assertEqual(pr.layer_of("", self.layers), "other")


class TestAttributeTable(unittest.TestCase):
    """属性表(data/attributes.json)がパースとビューワの共通の情報源であること。"""

    def test_キーが重複していない(self):
        keys = [a["key"] for a in config.attributes()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_元CSV列かパース時生成かのどちらかである(self):
        for a in config.attributes():
            self.assertTrue(
                ("source" in a) ^ bool(a.get("derived")),
                f"{a['key']} は source と derived のどちらか一方であるべき",
            )

    def test_パース側が読む列一覧と一致する(self):
        self.assertEqual(
            [a["source"] for a in config.attributes() if "source" in a],
            [src for src, _ in pr.KEEP_COLS],
        )

    def test_派生属性はパース側が知っているものだけ(self):
        self.assertLessEqual(pr.DERIVED, {"layer", "shape_name"})


class TestLayerDefinition(unittest.TestCase):
    def test_同じコードが複数のレイヤーに属していない(self):
        seen: dict[str, str] = {}
        for name, spec in config.layers().items():
            for code in spec["codes"]:
                self.assertNotIn(code, seen, f"コード {code} が {seen.get(code)} と {name} に重複")
                seen[code] = name

    def test_otherは受け皿なのでコードを持たない(self):
        self.assertEqual(config.layers()["other"]["codes"], [])


class TestPipelineConfig(unittest.TestCase):
    def test_表示開始ズームは収録範囲の中にある(self):
        self.assertGreaterEqual(config.DISPLAY_MIN_ZOOM, config.MIN_ZOOM)
        self.assertLessEqual(config.DISPLAY_MIN_ZOOM, config.MAX_ZOOM)

    def test_リポジトリ同梱の上限はGitHubの制限より小さい(self):
        self.assertLess(config.REPO_FILE_LIMIT_MB, 100)

    def test_R2のキーは月次とlatestで別物(self):
        self.assertNotEqual(config.month_key("202606"), config.latest_key())
        self.assertIn("202606", config.month_url("202606"))


if __name__ == "__main__":
    unittest.main()
