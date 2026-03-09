import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from render.fx_policy import (
    can_spawn_particle_fire,
    is_melee_wheel_token,
    pick_first_existing_texture_path,
    spawn_fireball_burst,
    should_cast_selected_spell,
)


class CombatFxPolicyTests(unittest.TestCase):
    def test_light_attack_does_not_cast_when_sword_selected(self):
        self.assertFalse(
            should_cast_selected_spell(light_pressed=True, selected_label="sword", explicit_cast=False)
        )

    def test_light_attack_casts_when_spell_selected(self):
        self.assertTrue(
            should_cast_selected_spell(light_pressed=True, selected_label="fireball", explicit_cast=False)
        )

    def test_explicit_cast_action_casts_without_light_attack(self):
        self.assertTrue(
            should_cast_selected_spell(light_pressed=False, selected_label="sword", explicit_cast=True)
        )

    def test_melee_token_detection(self):
        self.assertTrue(is_melee_wheel_token("sword"))
        self.assertTrue(is_melee_wheel_token("weapon_sword"))
        self.assertFalse(is_melee_wheel_token("nova"))

    def test_pick_first_existing_texture_path(self):
        existing = {"b.png", "c.png"}
        chosen = pick_first_existing_texture_path(
            ["a.png", "b.png", "c.png"], exists_fn=lambda p: p in existing
        )
        self.assertEqual("b.png", chosen)

    def test_pick_first_existing_texture_path_returns_empty_when_missing(self):
        chosen = pick_first_existing_texture_path(
            ["missing_1.png", "missing_2.png"], exists_fn=lambda _p: False
        )
        self.assertEqual("", chosen)

    def test_can_spawn_particle_fire_requires_spawn_method(self):
        self.assertFalse(can_spawn_particle_fire(object()))

        class _P:
            def spawnFireball(self, _pos):
                return 1

        self.assertTrue(can_spawn_particle_fire(_P()))

    def test_spawn_fireball_burst_uses_vec3_factory(self):
        seen = []

        class _P:
            def spawnFireball(self, pos):
                seen.append(pos)
                return 1

        class _Pos:
            x = 1.0
            y = 2.0
            z = 3.0

        created = []

        def _factory(x, y, z):
            created.append((x, y, z))
            return (x, y, z)

        count = spawn_fireball_burst(_P(), _Pos(), bursts=3, vec3_factory=_factory)
        self.assertEqual(3, count)
        self.assertEqual(3, len(seen))
        self.assertEqual([(1.0, 2.0, 3.0)] * 3, created)


if __name__ == "__main__":
    unittest.main()
