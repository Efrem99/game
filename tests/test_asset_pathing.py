import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.asset_pathing import existing_variants, normalize_asset_path, prefer_bam_path


class AssetPathingTests(unittest.TestCase):
    def test_normalize_asset_path_slashes(self):
        self.assertEqual(
            "assets/models/xbot/Xbot.glb",
            normalize_asset_path("assets\\models\\xbot\\Xbot.glb"),
        )

    def test_prefer_bam_when_variant_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "unit_model.glb"
            bam = root / "unit_model.bam"
            src.write_text("x", encoding="utf-8")
            bam.write_text("x", encoding="utf-8")
            resolved = prefer_bam_path(src.as_posix())
            self.assertEqual(bam.as_posix(), resolved)

    def test_keep_original_when_no_bam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "unit_model.glb"
            src.write_text("x", encoding="utf-8")
            resolved = prefer_bam_path(src.as_posix())
            self.assertEqual(src.as_posix(), resolved)

    def test_existing_variants_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "unit_model.glb"
            bam = root / "unit_model.bam"
            src.write_text("x", encoding="utf-8")
            bam.write_text("x", encoding="utf-8")
            rows = existing_variants(src.as_posix(), prefer_bam=True)
            self.assertEqual([bam.as_posix(), src.as_posix()], rows)


if __name__ == "__main__":
    unittest.main()
