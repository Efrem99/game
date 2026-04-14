import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player_combat_mixin import PlayerCombatMixin


class _FakeDataManager:
    def __init__(self):
        self.spells = {
            "fireball": {"mana_cost": 12, "damage": 20},
            "nova": {"mana_cost": 20, "damage": 15, "ultimate": True},
        }

    def get_spellbook_keys(self):
        return ["fireball", "nova"]

    def get_spell(self, key):
        return dict(self.spells.get(key, {}))


class _FakeCombatOwner(PlayerCombatMixin):
    def __init__(self):
        self.data_mgr = _FakeDataManager()
        self._spell_cache = []
        self._active_spell_idx = 0
        self._ultimate_spell_idx = 0


class SpellWheelPolicyTests(unittest.TestCase):
    def test_sword_slot_is_prepended_to_spell_wheel(self):
        owner = _FakeCombatOwner()
        owner._refresh_spell_cache()
        self.assertGreaterEqual(len(owner._spell_cache), 1)
        self.assertEqual("sword", str(owner._spell_cache[0]).lower())

    def test_ultimate_prefers_real_spell_not_sword_slot(self):
        owner = _FakeCombatOwner()
        owner._refresh_spell_cache()
        self.assertNotEqual(0, owner._ultimate_spell_idx)
        self.assertEqual("nova", str(owner._spell_cache[owner._ultimate_spell_idx]).lower())


if __name__ == "__main__":
    unittest.main()
