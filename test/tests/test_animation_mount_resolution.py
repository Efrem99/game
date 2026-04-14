import sys
import unittest
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from entities.player import Player
from entities.player_state_machine_mixin import PlayerStateMachineMixin
from entities.player_animation_config import ANIM_TOKEN_ALIASES, STATE_ANIM_FALLBACK


class _Velocity:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class _CharacterState:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.velocity = _Velocity(x=x, y=y, z=z)
        self.grounded = True
        self.health = 100.0
        self.inWater = False


class _TokenDummy:
    def __init__(self, kind):
        self._kind = kind

    def _current_mount_anim_kind(self):
        return self._kind


class _StateCtxDummy:
    def __init__(self):
        self.cs = None
        self.app = SimpleNamespace(vehicle_mgr=None)
        self._anim_state = "mounted_ship_idle"
        self._mount_anim_kind = "boat"
        self._is_flying = False
        self._context_flags = set()
        self._last_landing_impact_speed = 0.0
        self._was_grounded = True
        self._block_pressed = False
        self.combat = None

    def _get_action(self, _action):
        return False

    def _parkour_action_name(self):
        return ""


class AnimationMountResolutionTests(unittest.TestCase):
    def test_ship_idle_tokens_include_boat_manifest_key(self):
        dummy = _TokenDummy(kind="boat")
        tokens = Player._mount_state_context_tokens(dummy, "mounted_ship_idle")
        self.assertIn("mounted_idle_boat", tokens)

    def test_ship_move_tokens_include_boat_manifest_key(self):
        dummy = _TokenDummy(kind="boat")
        tokens = Player._mount_state_context_tokens(dummy, "mounted_ship_move")
        self.assertIn("mounted_move_boat", tokens)

    def test_ship_move_play_rate_scales_like_mounted_move(self):
        dummy = SimpleNamespace(
            cs=_CharacterState(x=4.0, y=0.0, z=0.0),
            walk_speed=2.0,
            run_speed=6.0,
            flight_speed=8.0,
            _anim_state="idle",
        )
        mounted_move = Player._anim_play_rate(dummy, "mounted_move")
        mounted_ship_move = Player._anim_play_rate(dummy, "mounted_ship_move")
        self.assertEqual(mounted_move, mounted_ship_move)
        self.assertGreater(mounted_ship_move, 1.0)

    def test_ship_state_context_keeps_mount_kind_when_vehicle_kind_missing_temporarily(self):
        dummy = _StateCtxDummy()
        context = PlayerStateMachineMixin._build_state_context(dummy)
        self.assertEqual("boat", context.get("mounted_kind"))
        self.assertEqual("boat", dummy._mount_anim_kind)

    def test_ship_mounting_resolves_boat_specific_clip_without_fallback(self):
        states_payload = json.loads((ROOT / "data" / "states" / "player_states.json").read_text(encoding="utf-8-sig"))
        actor_payload = json.loads((ROOT / "data" / "actors" / "player_animations.json").read_text(encoding="utf-8-sig"))

        class _ResolverDummy:
            pass

        dummy = _ResolverDummy()
        dummy._mount_anim_kind = "ship"
        dummy.app = SimpleNamespace(vehicle_mgr=None)
        dummy._state_anim_tokens = {
            str(item.get("name")).strip().lower(): str(item.get("animation")).strip()
            for item in states_payload.get("states", [])
            if isinstance(item, dict) and item.get("name") and item.get("animation")
        }
        dummy._state_anim_overrides = {
            str(state_name).strip().lower(): [str(token).strip() for token in tokens if isinstance(token, str)]
            for state_name, tokens in actor_payload.get("player", {}).items()
            if isinstance(tokens, list)
        }
        dummy._state_anim_fallback = dict(STATE_ANIM_FALLBACK)
        dummy._anim_token_aliases = dict(ANIM_TOKEN_ALIASES)
        dummy._available_anims = {
            str(entry.get("key")).strip()
            for entry in actor_payload.get("manifest", {}).get("sources", [])
            if isinstance(entry, dict) and entry.get("key")
        }

        def _normalize(token):
            return "".join(ch for ch in str(token or "").lower() if ch.isalnum())

        dummy._normalize_anim_key = _normalize
        dummy._current_mount_anim_kind = lambda: "boat"

        for name in ("_mount_state_context_tokens", "_iter_anim_candidates", "_resolve_anim_clip"):
            setattr(_ResolverDummy, name, getattr(Player, name))

        clip, source, _ = dummy._resolve_anim_clip(
            "mounting",
            include_state_fallback=False,
            include_global_fallback=False,
            with_meta=True,
        )

        self.assertEqual("mounting_boat", clip)
        self.assertEqual("mount_context", source)

    def test_ship_dismounting_resolves_boat_specific_clip_without_fallback(self):
        states_payload = json.loads((ROOT / "data" / "states" / "player_states.json").read_text(encoding="utf-8-sig"))
        actor_payload = json.loads((ROOT / "data" / "actors" / "player_animations.json").read_text(encoding="utf-8-sig"))

        class _ResolverDummy:
            pass

        dummy = _ResolverDummy()
        dummy._mount_anim_kind = "ship"
        dummy.app = SimpleNamespace(vehicle_mgr=None)
        dummy._state_anim_tokens = {
            str(item.get("name")).strip().lower(): str(item.get("animation")).strip()
            for item in states_payload.get("states", [])
            if isinstance(item, dict) and item.get("name") and item.get("animation")
        }
        dummy._state_anim_overrides = {
            str(state_name).strip().lower(): [str(token).strip() for token in tokens if isinstance(token, str)]
            for state_name, tokens in actor_payload.get("player", {}).items()
            if isinstance(tokens, list)
        }
        dummy._state_anim_fallback = dict(STATE_ANIM_FALLBACK)
        dummy._anim_token_aliases = dict(ANIM_TOKEN_ALIASES)
        dummy._available_anims = {
            str(entry.get("key")).strip()
            for entry in actor_payload.get("manifest", {}).get("sources", [])
            if isinstance(entry, dict) and entry.get("key")
        }

        def _normalize(token):
            return "".join(ch for ch in str(token or "").lower() if ch.isalnum())

        dummy._normalize_anim_key = _normalize
        dummy._current_mount_anim_kind = lambda: "boat"

        for name in ("_mount_state_context_tokens", "_iter_anim_candidates", "_resolve_anim_clip"):
            setattr(_ResolverDummy, name, getattr(Player, name))

        clip, source, _ = dummy._resolve_anim_clip(
            "dismounting",
            include_state_fallback=False,
            include_global_fallback=False,
            with_meta=True,
        )

        self.assertEqual("dismounting_boat", clip)
        self.assertEqual("mount_context", source)

    def test_declared_player_states_resolve_without_fallback_or_missing(self):
        states_payload = json.loads((ROOT / "data" / "states" / "player_states.json").read_text(encoding="utf-8-sig"))
        actor_payload = json.loads((ROOT / "data" / "actors" / "player_animations.json").read_text(encoding="utf-8-sig"))

        declared_states = [
            str(item.get("name", "")).strip().lower()
            for item in states_payload.get("states", [])
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        ]

        available = {"idle", "walk", "run"}
        for entry in actor_payload.get("manifest", {}).get("sources", []):
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("key") or entry.get("state") or entry.get("id") or "").strip()
            if key:
                available.add(key)

        class _ResolverDummy:
            pass

        dummy = _ResolverDummy()
        dummy._mount_anim_kind = "boat"
        dummy.app = SimpleNamespace(vehicle_mgr=None)
        dummy._state_anim_tokens = {
            str(item.get("name")).strip().lower(): str(item.get("animation")).strip()
            for item in states_payload.get("states", [])
            if isinstance(item, dict) and item.get("name") and item.get("animation")
        }
        dummy._state_anim_overrides = {
            str(state_name).strip().lower(): [str(token).strip() for token in tokens if isinstance(token, str)]
            for state_name, tokens in actor_payload.get("player", {}).items()
            if isinstance(tokens, list)
        }
        dummy._state_anim_fallback = dict(STATE_ANIM_FALLBACK)
        dummy._anim_token_aliases = dict(ANIM_TOKEN_ALIASES)
        dummy._available_anims = set(available)

        def _normalize(token):
            return "".join(ch for ch in str(token or "").lower() if ch.isalnum())

        def _kind():
            return "boat"

        dummy._normalize_anim_key = _normalize
        dummy._current_mount_anim_kind = _kind

        for name in ("_mount_state_context_tokens", "_iter_anim_candidates", "_resolve_anim_clip"):
            setattr(_ResolverDummy, name, getattr(Player, name))

        fallback_states = []
        missing_states = []
        for state_name in declared_states:
            strict_clip, strict_source, _ = dummy._resolve_anim_clip(
                state_name,
                include_state_fallback=False,
                include_global_fallback=False,
                with_meta=True,
            )
            strict_ok = bool(strict_clip) and not str(strict_source or "").startswith("alias:")
            if strict_ok:
                continue

            resolved = dummy._resolve_anim_clip(
                state_name,
                include_state_fallback=True,
                include_global_fallback=True,
            )
            if resolved:
                fallback_states.append(state_name)
            else:
                missing_states.append(state_name)

        self.assertEqual([], fallback_states)
        self.assertEqual([], missing_states)


if __name__ == "__main__":
    unittest.main()
