"""data/pipeline.json の tippecanoe ピン留めが CI で使える形か。

CI は tippecanoe_ref を checkout してビルドし、--version が tippecanoe_version と
一致することを確かめる。ここでは形式だけ見る(ネットワークには出ない)。
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PipelineConfigTest(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "data" / "pipeline.json").read_text(encoding="utf-8"))

    def test_tippecanoe_version_is_semver(self):
        self.assertRegex(self.cfg["tippecanoe_version"], r"^\d+\.\d+\.\d+$")

    def test_tippecanoe_ref_is_full_commit_sha(self):
        # 短縮SHAやブランチ名・タグ名は不可。felt/tippecanoe は版名のタグを打たなくなった。
        self.assertRegex(self.cfg["tippecanoe_ref"], r"^[0-9a-f]{40}$")

    def test_config_module_exposes_pin(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import config  # noqa: E402
        self.assertEqual(config.TIPPECANOE_VERSION, self.cfg["tippecanoe_version"])
        self.assertEqual(config.TIPPECANOE_REF, self.cfg["tippecanoe_ref"])
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", config.TIPPECANOE_REF))


if __name__ == "__main__":
    unittest.main()
