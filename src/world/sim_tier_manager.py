"""Python wrapper for the C++ AttentionManager.

Collects live entity data each frame, calls AttentionManager.update(),
then applies simulation tier changes to NPC/enemy proxies.

SimTier semantics:
  Hero       - full anims, full AI, full FX
  Active     - reduced AI tick-rate (~10 Hz), LOD1 geometry
  Simplified - pose-only, AI frozen, minimal FX
  Frozen     - no update, hidden or position-only
"""

from __future__ import annotations

import zlib

from utils.core_runtime import gc, HAS_CORE
from utils.logger import logger


class SimTierManager:
    # How often to run the full C++ tier computation (seconds).
    TICK_RATE = 1.0 / 15.0

    def __init__(
        self,
        app,
        max_dist: float = 120.0,
        budget_hero: int = 8,
        budget_active: int = 24,
        budget_simplified: int = 128,
    ):
        self._app = app
        self._accum = 0.0
        self._game_time = 0.0
        self._entity_registry: dict[int, object] = {}
        self._base_tick_rate = float(self.TICK_RATE)
        self._runtime_tick_rate = float(self._base_tick_rate)
        self._base_budgets = {
            "hero": int(budget_hero),
            "active": int(budget_active),
            "simplified": int(budget_simplified),
        }
        self._runtime_budget_scale = 1.0

        if HAS_CORE:
            self._mgr = gc.AttentionManager(max_dist, 0.20, 0.45)
            self._budget = gc.TierBudget()
            self._budget.maxHero = self._base_budgets["hero"]
            self._budget.maxActive = self._base_budgets["active"]
            self._budget.maxSimplified = self._base_budgets["simplified"]
            self._tier_frozen = gc.SimTier.Frozen
            self._tier_simpl = gc.SimTier.Simplified
            self._tier_active = gc.SimTier.Active
            self._tier_hero = gc.SimTier.Hero
        else:
            self._mgr = None
            self._budget = None

    def register(self, entity_id: int, entity_proxy) -> None:
        """Register an entity so it receives tier changes."""
        self._entity_registry[self._normalize_entity_id(entity_id)] = entity_proxy

    def unregister(self, entity_id: int) -> None:
        self._entity_registry.pop(self._normalize_entity_id(entity_id), None)

    def set_runtime_profile(self, tick_rate_hz=None, budget_scale=None) -> dict:
        """Adjust runtime cadence/budgets without mutating static defaults."""
        if tick_rate_hz is not None:
            try:
                hz = max(4.0, min(60.0, float(tick_rate_hz)))
                self._runtime_tick_rate = 1.0 / hz
            except Exception:
                self._runtime_tick_rate = self._base_tick_rate

        if budget_scale is not None:
            try:
                self._runtime_budget_scale = max(0.25, min(2.0, float(budget_scale)))
            except Exception:
                self._runtime_budget_scale = 1.0

        self._apply_budget_scale()
        return {
            "tick_rate_hz": 1.0 / max(1e-6, self._runtime_tick_rate),
            "budget_scale": float(self._runtime_budget_scale),
        }

    def _apply_budget_scale(self) -> None:
        if not HAS_CORE or not self._budget:
            return
        scale = max(0.25, min(2.0, float(self._runtime_budget_scale)))
        self._budget.maxHero = max(1, int(round(self._base_budgets["hero"] * scale)))
        self._budget.maxActive = max(1, int(round(self._base_budgets["active"] * scale)))
        self._budget.maxSimplified = max(
            1, int(round(self._base_budgets["simplified"] * scale))
        )

    def update(self, dt: float, cam_pos, cam_fwd, cam_ang_speed: float = 0.0) -> None:
        if not HAS_CORE or not self._mgr:
            return

        self._game_time += dt
        self._accum += dt

        if self._accum < self._runtime_tick_rate:
            return
        self._accum = 0.0

        objects: list[gc.AttentionObject] = []
        for eid, proxy in list(self._entity_registry.items()):
            try:
                obj = gc.AttentionObject()
                obj.id = eid
                pos = self._get_pos(proxy)
                obj.pos = gc.Vec3(pos[0], pos[1], pos[2])
                obj.radius = float(getattr(proxy, "_attention_radius", 1.0))
                obj.flags = self._gather_flags(proxy)
                objects.append(obj)
            except Exception as exc:
                logger.debug(f"[SimTierManager] Skipped entity {eid}: {exc}")

        if not objects:
            return

        self._mgr.setObjects(objects)

        cpp_cam_pos = gc.Vec3(cam_pos.x, cam_pos.y, cam_pos.z)
        cpp_cam_fwd = gc.Vec3(cam_fwd.x, cam_fwd.y, cam_fwd.z)
        self._mgr.update(
            cpp_cam_pos,
            cpp_cam_fwd,
            float(cam_ang_speed),
            self._game_time,
            self._budget,
        )

        for (eid, tier_int) in self._mgr.getTierChanges():
            proxy = self._entity_registry.get(eid)
            if proxy is None:
                continue
            try:
                self._apply_tier(proxy, tier_int)
            except Exception as exc:
                logger.debug(f"[SimTierManager] Tier apply failed for {eid}: {exc}")

        for eid in self._mgr.getPrewarmIds():
            proxy = self._entity_registry.get(eid)
            if proxy and hasattr(proxy, "_prewarm_lod"):
                try:
                    proxy._prewarm_lod()
                except Exception:
                    pass

    def _gather_flags(self, proxy) -> int:
        flags = 0
        if HAS_CORE:
            if getattr(proxy, "in_combat", False):
                flags |= gc.ATT_IN_COMBAT
            if getattr(proxy, "recently_hit", False):
                flags |= gc.ATT_RECENT
            if getattr(proxy, "is_quest_entity", False):
                flags |= gc.ATT_QUEST
            if getattr(proxy, "in_aoe_zone", False):
                flags |= gc.ATT_IN_AOE
            if getattr(proxy, "is_targeted", False):
                flags |= gc.ATT_TARGETED
            if getattr(proxy, "is_homing_target", False):
                flags |= gc.ATT_HOMING
        return flags

    def _apply_tier(self, proxy, tier_int: int) -> None:
        # tier_int: 0=Hero, 1=Active, 2=Simplified, 3=Frozen
        tier = tier_int

        if hasattr(proxy, "_sim_tier") and proxy._sim_tier == tier:
            return
        if hasattr(proxy, "_sim_tier"):
            proxy._sim_tier = tier

        if tier == 0:
            self._set_full(proxy)
        elif tier == 1:
            self._set_active(proxy)
        elif tier == 2:
            self._set_simplified(proxy)
        else:
            self._set_frozen(proxy)

    @staticmethod
    def _normalize_entity_id(entity_id) -> int:
        if isinstance(entity_id, bool):
            return int(entity_id)
        if isinstance(entity_id, int):
            return entity_id
        text = str(entity_id or "").strip()
        if not text:
            return 0
        return int(zlib.crc32(text.encode("utf-8")) & 0x7FFFFFFF)

    def _set_full(self, proxy):
        if hasattr(proxy, "actor"):
            try:
                proxy.actor.show()
            except Exception:
                pass
        _safe_call(proxy, "enable_ai")
        _safe_call(proxy, "enable_full_anim")
        _safe_call(proxy, "set_ai_tick_rate", 1.0 / 30.0)

    def _set_active(self, proxy):
        if hasattr(proxy, "actor"):
            try:
                proxy.actor.show()
            except Exception:
                pass
        _safe_call(proxy, "enable_ai")
        _safe_call(proxy, "set_ai_tick_rate", 1.0 / 10.0)

    def _set_simplified(self, proxy):
        if hasattr(proxy, "actor"):
            try:
                proxy.actor.show()
            except Exception:
                pass
        _safe_call(proxy, "disable_ai")
        _safe_call(proxy, "set_ai_tick_rate", 1.0 / 2.0)

    def _set_frozen(self, proxy):
        _safe_call(proxy, "disable_ai")

    @staticmethod
    def _get_pos(proxy) -> tuple[float, float, float]:
        if hasattr(proxy, "actor"):
            p = proxy.actor.getPos()
            return (p.x, p.y, p.z)
        pos = getattr(proxy, "pos", None)
        if pos is not None:
            if hasattr(pos, "x"):
                return (float(pos.x), float(pos.y), float(pos.z))
            if isinstance(pos, (list, tuple)) and len(pos) >= 3:
                return (float(pos[0]), float(pos[1]), float(pos[2]))
        return (0.0, 0.0, 0.0)


def _safe_call(obj, method: str, *args):
    fn = getattr(obj, method, None)
    if callable(fn):
        try:
            fn(*args)
        except Exception:
            pass
