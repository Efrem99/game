"""Python wrapper for the C++ AttentionManager.

Collects live entity data each frame, calls AttentionManager.update(),
then applies SimTier changes to the actual NPC/enemy objects.

SimTier semantics:
  Hero       – full anims, full AI, full FX
  Active     – reduced AI tick-rate (~10 Hz), LOD1 geometry
  Simplified – pose-only, AI frozen, minimal FX
  Frozen     – no update, hidden or position-only

Usage in app.py::
    self.sim_tier_mgr = SimTierManager(base)
    # each frame:
    self.sim_tier_mgr.update(dt, cam_pos, cam_fwd, cam_ang_speed)
"""

from __future__ import annotations

import math
from direct.showbase.ShowBaseGlobal import globalClock
from utils.logger import logger

try:
    import game_core as gc
    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False


class SimTierManager:
    # How often to run the full C++ tier computation (seconds).
    # Every other frame the result is just applied without re-computing.
    TICK_RATE = 1.0 / 15.0   # 15 Hz is plenty

    def __init__(self, app, max_dist: float = 120.0,
                 budget_hero: int = 8,
                 budget_active: int = 24,
                 budget_simplified: int = 128):
        self._app = app
        self._accum = 0.0
        self._game_time = 0.0
        self._entity_registry: dict[int, object] = {}   # id → entity proxy

        if HAS_CORE:
            self._mgr = gc.AttentionManager(max_dist, 0.20, 0.45)
            self._budget = gc.TierBudget()
            self._budget.maxHero       = budget_hero
            self._budget.maxActive     = budget_active
            self._budget.maxSimplified = budget_simplified
            self._tier_frozen    = gc.SimTier.Frozen
            self._tier_simpl     = gc.SimTier.Simplified
            self._tier_active    = gc.SimTier.Active
            self._tier_hero      = gc.SimTier.Hero
        else:
            self._mgr = None
            self._budget = None

    # ───────────────────────────────────────────────────────────
    # Registration  (call when entity is spawned / despawned)
    # ───────────────────────────────────────────────────────────

    def register(self, entity_id: int, entity_proxy) -> None:
        """Register an entity so it receives tier changes."""
        self._entity_registry[entity_id] = entity_proxy

    def unregister(self, entity_id: int) -> None:
        self._entity_registry.pop(entity_id, None)

    # ───────────────────────────────────────────────────────────
    # Main update  (call each gameplay frame)
    # ───────────────────────────────────────────────────────────

    def update(self, dt: float, cam_pos, cam_fwd, cam_ang_speed: float = 0.0) -> None:
        if not HAS_CORE or not self._mgr:
            return

        self._game_time += dt
        self._accum += dt

        if self._accum < self.TICK_RATE:
            return
        self._accum = 0.0

        # Build object list from registered entities
        objects: list[gc.AttentionObject] = []
        for eid, proxy in list(self._entity_registry.items()):
            try:
                obj = gc.AttentionObject()
                obj.id = eid

                pos = self._get_pos(proxy)
                obj.pos = gc.Vec3(pos[0], pos[1], pos[2])
                obj.radius = float(getattr(proxy, "_attention_radius", 1.0))
                obj.flags  = self._gather_flags(proxy)
                objects.append(obj)
            except Exception as exc:
                logger.debug(f"[SimTierManager] Skipped entity {eid}: {exc}")

        if not objects:
            return

        self._mgr.setObjects(objects)

        cpp_cam_pos = gc.Vec3(cam_pos.x, cam_pos.y, cam_pos.z)
        cpp_cam_fwd = gc.Vec3(cam_fwd.x, cam_fwd.y, cam_fwd.z)

        self._mgr.update(cpp_cam_pos, cpp_cam_fwd, float(cam_ang_speed),
                         self._game_time, self._budget)

        # Apply tier changes
        for (eid, tier_int) in self._mgr.getTierChanges():
            proxy = self._entity_registry.get(eid)
            if proxy is None:
                continue
            try:
                self._apply_tier(proxy, tier_int)
            except Exception as exc:
                logger.debug(f"[SimTierManager] Tier apply failed for {eid}: {exc}")

        # Prewarm requests (optional: preload LODs)
        for eid in self._mgr.getPrewarmIds():
            proxy = self._entity_registry.get(eid)
            if proxy and hasattr(proxy, "_prewarm_lod"):
                try:
                    proxy._prewarm_lod()
                except Exception:
                    pass

    # ───────────────────────────────────────────────────────────
    # Flag gathering from entity properties
    # ───────────────────────────────────────────────────────────

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

    # ───────────────────────────────────────────────────────────
    # Tier application to entity proxy
    # ───────────────────────────────────────────────────────────

    def _apply_tier(self, proxy, tier_int: int) -> None:
        # tier_int: 0=Hero, 1=Active, 2=Simplified, 3=Frozen
        # Generic interface: proxy may expose optional methods/flags
        tier = tier_int

        if hasattr(proxy, "_sim_tier") and proxy._sim_tier == tier:
            return  # no change
        if hasattr(proxy, "_sim_tier"):
            proxy._sim_tier = tier

        if tier == 0:   # Hero — full
            self._set_full(proxy)
        elif tier == 1: # Active — light reduction
            self._set_active(proxy)
        elif tier == 2: # Simplified — pose only
            self._set_simplified(proxy)
        else:           # Frozen
            self._set_frozen(proxy)

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
        _safe_call(proxy, "set_ai_tick_rate", 1.0 / 10.0)  # 10 Hz

    def _set_simplified(self, proxy):
        if hasattr(proxy, "actor"):
            try:
                proxy.actor.show()
            except Exception:
                pass
        _safe_call(proxy, "disable_ai")
        _safe_call(proxy, "set_ai_tick_rate", 1.0 / 2.0)   # 2 Hz pose

    def _set_frozen(self, proxy):
        _safe_call(proxy, "disable_ai")
        # Don't hide — just freeze

    # ───────────────────────────────────────────────────────────
    # Utility
    # ───────────────────────────────────────────────────────────

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
