# -*- coding: utf-8 -*-
"""品質ゲート。人のレビューを挟まずに公開するための最後の砦。

前回の dataset.json と比べて「明らかにおかしい」ものを止める。
元データは都道府県警察ごとに提供が変わるので、増減そのものは異常ではない。
止めたいのは「取得や解析が壊れた結果、静かに減った」ケース。
"""
from __future__ import annotations

DEFAULT_MAX_FEATURE_DROP = 0.05


def check(new: dict, prev: dict, max_drop: float = DEFAULT_MAX_FEATURE_DROP) -> list[str]:
    """公開を止める理由を並べて返す。空なら通す。前回が無ければ何も止めない。"""
    fails: list[str] = []
    if not prev:
        return fails

    if new["year_month"] <= prev.get("year_month", ""):
        fails.append(
            f"対象年月が前回より新しくない ({new['year_month']} <= {prev.get('year_month')})"
        )

    pn, nn = prev.get("features_total", 0), new["features_total"]
    if pn and nn < pn * (1 - max_drop):
        fails.append(f"フィーチャ数が前回比 {(1 - nn / pn) * 100:.1f}% 減 ({pn:,} → {nn:,})")

    for layer, cur in new["by_layer"].items():
        was = prev.get("by_layer", {}).get(layer, {}).get("n", 0)
        if was and cur["n"] == 0:
            fails.append(f"レイヤー {layer} が0件になった (前回 {was:,})")

    lost = set(prev.get("prefectures", [])) - set(new["prefectures"])
    if lost:
        fails.append(f"都道府県が欠けた: {sorted(lost)}")

    return fails
