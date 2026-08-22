# -*- coding: utf-8 -*-
"""品質ゲートのテスト。

ここが壊れると、壊れたデータが無人で公開される。4条件それぞれを押さえる。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import gate  # noqa: E402


def ds(ym="202607", n=1000, layers=None, prefs=("01", "13")):
    return {
        "year_month": ym,
        "features_total": n,
        "by_layer": layers if layers is not None else {"stop": {"n": n}},
        "prefectures": list(prefs),
    }


class TestGate(unittest.TestCase):
    def test_前回が無ければ何も止めない(self):
        self.assertEqual(gate.check(ds(), {}), [])

    def test_通常の更新は通る(self):
        self.assertEqual(gate.check(ds("202607", 1000), ds("202606", 990)), [])

    def test_対象年月が同じなら止める(self):
        fails = gate.check(ds("202606"), ds("202606"))
        self.assertTrue(any("対象年月" in f for f in fails))

    def test_対象年月が巻き戻ったら止める(self):
        fails = gate.check(ds("202605"), ds("202606"))
        self.assertTrue(any("対象年月" in f for f in fails))

    def test_フィーチャ数が5パーセント超減ったら止める(self):
        fails = gate.check(ds("202607", 940), ds("202606", 1000))
        self.assertTrue(any("フィーチャ数" in f for f in fails))

    def test_ちょうど5パーセント減は通す(self):
        self.assertEqual(gate.check(ds("202607", 950), ds("202606", 1000)), [])

    def test_しきい値は変えられる(self):
        prev, new = ds("202606", 1000), ds("202607", 900)
        self.assertEqual(gate.check(new, prev, max_drop=0.2), [])
        self.assertTrue(gate.check(new, prev, max_drop=0.01))

    def test_前回あったレイヤーが0件になったら止める(self):
        prev = ds("202606", 1000, {"stop": {"n": 500}, "signal": {"n": 500}})
        new = ds("202607", 1000, {"stop": {"n": 1000}, "signal": {"n": 0}})
        fails = gate.check(new, prev)
        self.assertTrue(any("signal" in f for f in fails))

    def test_前回無かったレイヤーが0件でも止めない(self):
        prev = ds("202606", 1000, {"stop": {"n": 1000}})
        new = ds("202607", 1000, {"stop": {"n": 1000}, "priority": {"n": 0}})
        self.assertEqual(gate.check(new, prev), [])

    def test_都道府県が欠けたら止める(self):
        fails = gate.check(ds(prefs=("01",)), ds("202606", 990, prefs=("01", "13")))
        self.assertTrue(any("都道府県" in f and "13" in f for f in fails))

    def test_都道府県が増えるのは通す(self):
        self.assertEqual(
            gate.check(ds(prefs=("01", "13", "27")), ds("202606", 990, prefs=("01", "13"))),
            [],
        )

    def test_複数の違反をすべて並べる(self):
        prev = ds("202606", 1000, {"stop": {"n": 500}}, ("01", "13"))
        new = ds("202605", 100, {"stop": {"n": 0}}, ("01",))
        self.assertEqual(len(gate.check(new, prev)), 4)


if __name__ == "__main__":
    unittest.main()
