"""
HazardManager - Environmental Hazard Zones (Lava, Swamp, Water, Fire)
Manages damage-over-time zones, movement penalties, and VFX triggers for
environmental hazards placed via the Level Editor or world layout.
"""
import math
from utils.logger import logger


HAZARD_PRESETS = {
    "lava_pool": {
        "damage_per_sec": 25.0,
        "slow_factor": 0.0,        # No slow, just burn
        "vfx": "fire_intense",
        "status": "burning",
        "color": (1.0, 0.28, 0.0, 0.88),
    },
    "swamp_pool": {
        "damage_per_sec": 2.0,
        "slow_factor": 0.45,       # 45% speed reduction
        "vfx": "swamp_bubble",
        "status": "slowed",
        "color": (0.18, 0.36, 0.1, 0.80),
    },
    "water_pool": {
        "damage_per_sec": 0.0,
        "slow_factor": 0.25,
        "vfx": "water_splash",
        "status": "wet",
        "color": (0.18, 0.5, 0.82, 0.65),
    },
    "fire_area": {
        "damage_per_sec": 12.0,
        "slow_factor": 0.0,
        "vfx": "fire_medium",
        "status": "burning",
        "color": (1.0, 0.5, 0.0, 0.72),
    },
    "poison_cloud": {
        "damage_per_sec": 5.0,
        "slow_factor": 0.15,
        "vfx": "poison_gas",
        "status": "poisoned",
        "color": (0.4, 0.8, 0.2, 0.55),
    },
    "blizzard_zone": {
        "damage_per_sec": 3.0,
        "slow_factor": 0.35,
        "vfx": "blizzard",
        "status": "frozen",
        "color": (0.65, 0.88, 1.0, 0.60),
    },
}


class HazardZone:
    """A single active hazard zone in the world."""
    def __init__(self, zone_id, zone_type, pos, radius=3.0):
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.pos = pos          # [x, y, z]
        self.radius = radius
        self.preset = HAZARD_PRESETS.get(zone_type, {})
        self.active = True
        self._vfx_node = None   # Assigned by world when VFX is spawned

    def contains_point(self, x, y):
        """2D distance check (XY plane, ignores Z for triggering)."""
        dx = x - self.pos[0]
        dy = y - self.pos[1]
        return math.sqrt(dx * dx + dy * dy) <= self.radius


class HazardManager:
    """
    Polls all active hazard zones every frame and applies effects to
    the player (and optionally NPCs) that enter them.
    """

    def __init__(self, app):
        self.app = app
        self.zones: dict[str, HazardZone] = {}
        self._accumulated = {}   # zone_id -> accumulated time inside
        self.app.taskMgr.add(self._update, "hazard_manager_task")
        logger.info("[HazardManager] Initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_zone(self, zone_id: str, zone_type: str, pos, radius: float = 3.0):
        """Register a new hazard zone (called by EditorManager on spawn or world init)."""
        zone = HazardZone(zone_id, zone_type, list(pos), radius)
        self.zones[zone_id] = zone
        logger.info(f"[HazardManager] Zone registered: {zone_id} ({zone_type}) r={radius}")

    def remove_zone(self, zone_id: str):
        self.zones.pop(zone_id, None)
        self._accumulated.pop(zone_id, None)

    def clear_all(self):
        self.zones.clear()
        self._accumulated.clear()

    def get_zones_data(self) -> list:
        """Returns serializable list for bridge / bake system."""
        out = []
        for z in self.zones.values():
            out.append({
                "id": z.zone_id,
                "type": z.zone_type,
                "pos": z.pos,
                "radius": z.radius,
            })
        return out

    # ------------------------------------------------------------------
    # Internal update loop
    # ------------------------------------------------------------------

    def _update(self, task):
        if not self.zones:
            return task.cont

        # Get player position
        player = getattr(self.app, "player", None)
        if not player:
            return task.cont

        player_np = getattr(player, "node", None) or getattr(player, "actor", None)
        if not player_np:
            return task.cont

        try:
            ppos = player_np.getPos()
            px, py = ppos.x, ppos.y
        except Exception:
            return task.cont

        dt = globalClock.getDt()
        player_in_any_zone = False

        for zone in list(self.zones.values()):
            if not zone.active:
                continue

            inside = zone.contains_point(px, py)

            if inside:
                player_in_any_zone = True
                acc = self._accumulated.get(zone.zone_id, 0.0) + dt
                self._accumulated[zone.zone_id] = acc

                self._apply_effects(player, zone, dt)
            else:
                if zone.zone_id in self._accumulated:
                    self._on_exit(player, zone)
                    self._accumulated.pop(zone.zone_id, None)

        return task.cont

    def _apply_effects(self, player, zone: HazardZone, dt: float):
        preset = zone.preset
        if not preset:
            return

        # --- Damage over time ---
        dps = preset.get("damage_per_sec", 0.0)
        if dps > 0:
            dmg = dps * dt
            if hasattr(player, "take_damage"):
                player.take_damage(dmg, source=zone.zone_type)
            elif hasattr(player, "hp"):
                player.hp = max(0, player.hp - dmg)

        # --- Movement slow ---
        slow = preset.get("slow_factor", 0.0)
        if slow > 0:
            if hasattr(player, "speed_multiplier"):
                player.speed_multiplier = max(0.1, 1.0 - slow)

        # --- Status effect ---
        status = preset.get("status", "")
        if status and hasattr(player, "apply_status"):
            player.apply_status(status, duration=0.5)  # Refresh every frame while inside

    def _on_exit(self, player, zone: HazardZone):
        """Remove slow when the player leaves the zone."""
        slow = zone.preset.get("slow_factor", 0.0)
        if slow > 0 and hasattr(player, "speed_multiplier"):
            player.speed_multiplier = 1.0

    # ------------------------------------------------------------------
    # World layout loading
    # ------------------------------------------------------------------

    def load_from_layout(self, layout: dict):
        """Load hazard zones from the world layout dict (called by SharuanWorld)."""
        hazards = layout.get("hazard_zones", [])
        for entry in hazards:
            if not isinstance(entry, dict):
                continue
            z_id = str(entry.get("id", ""))
            z_type = str(entry.get("type", "lava_pool"))
            pos = entry.get("pos", [0, 0, 0])
            radius = float(entry.get("radius", 3.0))
            if z_id:
                self.register_zone(z_id, z_type, pos, radius)
