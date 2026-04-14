import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mixamo_player_fetch as mpf


def test_mixamo_player_fetch_exposes_core_transition_targets():
    for key in ("jumping", "falling", "landing", "weapon_unsheathe", "weapon_sheathe"):
        assert key in mpf.TARGET_QUERIES
        assert isinstance(mpf.TARGET_QUERIES[key], list)
        assert any(str(item).strip() for item in mpf.TARGET_QUERIES[key])


def test_mixamo_player_fetch_loop_defaults_match_transition_intent():
    assert mpf.DEFAULT_LOOPS["jumping"] is False
    assert mpf.DEFAULT_LOOPS["falling"] is True
    assert mpf.DEFAULT_LOOPS["landing"] is False
    assert mpf.DEFAULT_LOOPS["weapon_unsheathe"] is False
    assert mpf.DEFAULT_LOOPS["weapon_sheathe"] is False
