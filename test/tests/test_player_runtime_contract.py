import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_input_mixin import PlayerInputMixin


class _AppAcceptStub:
    def __init__(self):
        self.accept_calls = []

    def accept(self, event_name, handler, args):
        self.accept_calls.append((str(event_name), handler, tuple(args)))


class _InputDataManagerStub:
    def __init__(self):
        self.controls = {
            "bindings": {
                "forward": "w",
                "backward": "s",
                "left": "a",
                "right": "d",
            },
            "gamepad_bindings": {},
        }

    def get_binding(self, action):
        return self.controls["bindings"].get(action, "")


class _InputSetupDummy:
    _setup_input = Player._setup_input
    _normalize_binding_token = PlayerInputMixin._normalize_binding_token
    _key_down = PlayerInputMixin._key_down
    _key_up = PlayerInputMixin._key_up
    _video_bot_input_locked = PlayerInputMixin._video_bot_input_locked

    def __init__(self):
        self.data_mgr = _InputDataManagerStub()
        self.app = _AppAcceptStub()
        self._keys = {}
        self._consumed = {}


class _SpellDataManagerStub:
    def __init__(self):
        self.spells = {
            "fireball": {"mana_cost": 12, "damage": 20},
            "nova": {"mana_cost": 20, "damage": 15, "ultimate": True},
        }

    def get_spellbook_keys(self):
        return ["fireball", "nova"]

    def get_spell(self, key):
        return dict(self.spells.get(key, {}))


class _SpellCacheDummy:
    _refresh_spell_cache = Player._refresh_spell_cache

    def __init__(self):
        self.data_mgr = _SpellDataManagerStub()
        self._spell_cache = []
        self._active_spell_idx = 0
        self._ultimate_spell_idx = 0


class _InventoryUIStub:
    def show(self):
        return None

    def hide(self):
        return None


class _StateManagerStub:
    def __init__(self):
        self.current_state = "PLAYING"

    def set_state(self, state):
        self.current_state = state


class _PlayerUpdateDummy:
    update = getattr(Player, "update", None)

    def __init__(self, interacted=False, npc_interact_result=False, story_interact_result=False):
        self._quest_calls = []
        self.app = types.SimpleNamespace(
            camera_director=None,
            state_mgr=_StateManagerStub(),
            GameState=types.SimpleNamespace(INVENTORY="INVENTORY", PLAYING="PLAYING"),
            inventory_ui=_InventoryUIStub(),
            quest_mgr=types.SimpleNamespace(try_interact=lambda _pos: self._quest_calls.append("quest")),
        )
        self._skill_wheel_open = False
        self.cs = None
        self._python_updates = []
        self._combat_updates = []
        self._brain_updates = []
        self.actor = types.SimpleNamespace(getPos=lambda *_args, **_kwargs: (0.0, 0.0, 0.0))
        self._interacted = bool(interacted)
        self._npc_interact_result = bool(npc_interact_result)
        self._story_interact_result = bool(story_interact_result)
        self._npc_calls = []
        self._story_calls = []

    def _once_action(self, action):
        if action == "interact" and self._interacted:
            self._interacted = False
            return True
        return False

    def _update_skill_wheel_input(self):
        return None

    def _update_damage_feedback(self):
        return None

    def _tick_damage_vignette_state(self, _dt):
        return None

    def _get_move_axes(self):
        return (0.25, 1.0)

    def _sync_stealth_input(self):
        return None

    def _sync_block_state_edges(self):
        return None

    def _try_vehicle_interact(self):
        return False

    def _update_vehicle_control(self, _dt, _cam_yaw, _mx, _my):
        return False

    def _try_npc_interact(self):
        self._npc_calls.append("npc")
        return self._npc_interact_result

    def _try_story_interact(self):
        self._story_calls.append("story")
        return self._story_interact_result

    def _update_combat(self, dt):
        self._combat_updates.append(float(dt))

    def _proc_animate(self, dt):
        self._proc_animate_dt = float(dt)

    def _update_python_movement(self, dt, cam_yaw, mx=None, my=None):
        self._python_updates.append((float(dt), float(cam_yaw), float(mx), float(my)))

    def _update_brain_runtime(self, mx, my, cam_yaw):
        self._brain_updates.append((float(mx), float(my), float(cam_yaw)))


class _PlayerEffectsDummy:
    apply_effect = getattr(Player, "apply_effect", None)
    take_damage = getattr(Player, "take_damage", None)

    def __init__(self):
        self.cs = types.SimpleNamespace(
            health=40.0,
            maxHealth=100.0,
            mana=10.0,
            maxMana=50.0,
            stamina=5.0,
            maxStamina=20.0,
        )
        self.hp = 40.0
        self.max_hp = 100.0
        self._dead_flag = False
        self._death_time = 0.0
        self._respawn_requested = False
        self._incoming_damage_amount = 0.0
        self._incoming_damage_type = ""
        self._registered_damage = []

    def register_incoming_damage(self, amount=0.0, damage_type="physical"):
        dmg = max(0.0, float(amount))
        dtype = str(damage_type or "physical")
        self._registered_damage.append((dmg, dtype))
        self._incoming_damage_amount = max(float(self._incoming_damage_amount), dmg)
        self._incoming_damage_type = dtype


class PlayerRuntimeContractTests(unittest.TestCase):
    def test_setup_input_uses_player_input_mixin_runtime_wiring(self):
        dummy = _InputSetupDummy()

        dummy._setup_input()

        self.assertEqual("w", dummy._bindings["forward"])
        self.assertIn("w", dummy._keys)
        self.assertTrue(dummy.app.accept_calls)
        self.assertIn(("w", dummy._key_down, ("w",)), dummy.app.accept_calls)

    def test_refresh_spell_cache_uses_spell_wheel_policy(self):
        dummy = _SpellCacheDummy()

        dummy._refresh_spell_cache()

        self.assertGreaterEqual(len(dummy._spell_cache), 2)
        self.assertEqual("sword", str(dummy._spell_cache[0]).lower())
        self.assertEqual("nova", str(dummy._spell_cache[dummy._ultimate_spell_idx]).lower())

    def test_player_exposes_update_runtime_entrypoint(self):
        self.assertTrue(callable(getattr(Player, "update", None)))

    def test_update_routes_python_runtime_when_core_state_is_missing(self):
        self.assertTrue(callable(_PlayerUpdateDummy.update))
        dummy = _PlayerUpdateDummy()

        dummy.update(0.25, 90.0)

        self.assertEqual([(0.25, 90.0, 0.25, 1.0)], dummy._python_updates)
        self.assertEqual([0.25], dummy._combat_updates)
        self.assertEqual([(0.25, 1.0, 90.0)], dummy._brain_updates)

    def test_update_routes_interact_to_npc_before_story_and_quest(self):
        dummy = _PlayerUpdateDummy(interacted=True, npc_interact_result=True, story_interact_result=False)

        dummy.update(0.25, 90.0)

        self.assertEqual(["npc"], dummy._npc_calls)
        self.assertEqual([], dummy._story_calls)
        self.assertEqual([], dummy._quest_calls)

    def test_update_falls_back_to_story_then_quest_when_npc_does_not_handle_interact(self):
        dummy = _PlayerUpdateDummy(interacted=True, npc_interact_result=False, story_interact_result=False)

        dummy.update(0.25, 90.0)

        self.assertEqual(["npc"], dummy._npc_calls)
        self.assertEqual(["story"], dummy._story_calls)
        self.assertEqual(["quest"], dummy._quest_calls)

    def test_apply_effect_supports_ratio_based_resource_updates(self):
        self.assertTrue(callable(_PlayerEffectsDummy.apply_effect))
        dummy = _PlayerEffectsDummy()

        healed = dummy.apply_effect("heal", 0.25)
        restored_mana = dummy.apply_effect("mana", 0.50)
        restored_stamina = dummy.apply_effect("stamina", 0.50)

        self.assertTrue(healed)
        self.assertTrue(restored_mana)
        self.assertTrue(restored_stamina)
        self.assertEqual(65.0, dummy.cs.health)
        self.assertEqual(35.0, dummy.cs.mana)
        self.assertEqual(15.0, dummy.cs.stamina)

    def test_take_damage_updates_health_and_damage_feedback_state(self):
        self.assertTrue(callable(_PlayerEffectsDummy.take_damage))
        dummy = _PlayerEffectsDummy()

        applied = dummy.take_damage(18.0, "fire")

        self.assertTrue(applied)
        self.assertEqual(22.0, dummy.cs.health)
        self.assertEqual([(18.0, "fire")], dummy._registered_damage)
        self.assertEqual("fire", dummy._incoming_damage_type)
        self.assertEqual(18.0, dummy._incoming_damage_amount)


if __name__ == "__main__":
    unittest.main()
