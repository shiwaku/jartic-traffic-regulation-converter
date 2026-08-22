# -*- coding: utf-8 -*-
"""GitHub Actions への出力。ローカル実行では何もしない。

ワークフロー側の条件分岐は、ここで書いた step output だけを見る。
同じ判定を bash で書き直さないための境界。
"""
from __future__ import annotations

import os


def emit(**kv: str) -> None:
    """step output を書く(steps.<id>.outputs.<key> で読める)。"""
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def summary(markdown: str) -> None:
    """実行結果ページに残す要約。人が後から見るのはこれ。"""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(markdown.rstrip() + "\n")
