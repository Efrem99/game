import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import app


class AppCachePolicyTests(unittest.TestCase):
    def test_runtime_tests_keep_panda_model_cache_enabled_by_default(self):
        should_disable = app._should_disable_panda_model_cache_for_runtime_tests(
            runtime_test_boot=True,
            env={},
        )

        self.assertFalse(should_disable)

    def test_explicit_opt_out_can_disable_panda_model_cache(self):
        should_disable = app._should_disable_panda_model_cache_for_runtime_tests(
            runtime_test_boot=True,
            env={"XBOT_DISABLE_PANDA_MODEL_CACHE": "1"},
        )

        self.assertTrue(should_disable)

    def test_non_runtime_sessions_do_not_disable_panda_model_cache(self):
        should_disable = app._should_disable_panda_model_cache_for_runtime_tests(
            runtime_test_boot=False,
            env={"XBOT_DISABLE_PANDA_MODEL_CACHE": "1"},
        )

        self.assertFalse(should_disable)


if __name__ == "__main__":
    unittest.main()
