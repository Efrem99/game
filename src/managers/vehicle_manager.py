import math
from typing import Dict, List, Optional, Tuple

from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import LColor, Vec3

from utils.logger import logger
from world.sharuan_world import mk_box, mk_cone, mk_cyl


class VehicleManager:
    """Mountable transport system with data-driven spawns and tuning."""

    DEFAULT_SPAWNS = [
        {"id": "horse_1", "kind": "horse", "pos": [9.0, 6.0], "heading": 25.0},
        {"id": "horse_2", "kind": "horse", "pos": [13.0, 9.0], "heading": 205.0},
        {"id": "carriage_1", "kind": "carriage", "pos": [-11.0, 4.0], "heading": 90.0},
        {"id": "ship_1", "kind": "ship", "pos": [0.0, -77.0], "heading": 180.0},
    ]

    def __init__(self, app):
        self.app = app
        self.vehicles: List[Dict] = []
        self._vehicles_by_id: Dict[str, Dict] = {}
        self.mounted_vehicle_id: Optional[str] = None
        self._bootstrapped = False
        self._nav_zones: List[Dict] = []

    @property
    def is_mounted(self) -> bool:
        return bool(self.mounted_vehicle_id)

    def mounted_vehicle(self) -> Optional[Dict]:
        if not self.mounted_vehicle_id:
            return None
        return self._vehicles_by_id.get(self.mounted_vehicle_id)

    def spawn_default_vehicles(self):
        if self._bootstrapped or not getattr(self.app, "render", None):
            return

        self._load_navigation_zones()
        entries = self._spawn_entries_from_config()
        for idx, entry in enumerate(entries):
            vehicle = self._spawn_vehicle_from_entry(entry, fallback_index=idx)
            if not vehicle:
                continue
            self.vehicles.append(vehicle)
            self._vehicles_by_id[vehicle["id"]] = vehicle

        self._bootstrapped = True
        logger.info(
            f"[VehicleManager] Spawned transports: {len(self.vehicles)} "
            f"(nav_zones={len(self._nav_zones)})"
        )

    def export_state(self) -> Dict:
        vehicles = []
        vehicle_positions = {}
        for vehicle in self.vehicles:
            node = vehicle["node"]
            pos = node.getPos(self.app.render)
            vel = vehicle.get("velocity", Vec3(0, 0, 0))
            row = {
                "id": vehicle["id"],
                "kind": vehicle["kind"],
                "position": [float(pos.x), float(pos.y), float(pos.z)],
                "heading": float(node.getH(self.app.render)),
                "velocity": [float(vel.x), float(vel.y), float(vel.z)],
            }
            vehicles.append(row)
            vehicle_positions[vehicle["id"]] = dict(row)
            vehicle_positions[vehicle["id"]].pop("id", None)

        mounted = self.mounted_vehicle()
        mount_state = {
            "is_mounted": bool(self.mounted_vehicle_id),
            "vehicle_id": self.mounted_vehicle_id,
            "kind": str(mounted.get("kind", "")) if isinstance(mounted, dict) else "",
        }
        return {
            "mounted_vehicle_id": self.mounted_vehicle_id,  # legacy key
            "mount_state": mount_state,
            "vehicle_positions": vehicle_positions,
            "vehicles": vehicles,  # legacy key
        }

    def import_state(self, payload, player=None):
        if not isinstance(payload, dict):
            return

        rows = []
        raw_positions = payload.get("vehicle_positions")
        if isinstance(raw_positions, dict):
            for vehicle_id, row in raw_positions.items():
                if not isinstance(row, dict):
                    continue
                merged = dict(row)
                merged["id"] = str(vehicle_id)
                rows.append(merged)
        elif isinstance(payload.get("vehicles"), list):
            rows = [item for item in payload.get("vehicles", []) if isinstance(item, dict)]

        for item in rows:
            vehicle = self._vehicles_by_id.get(str(item.get("id", "")))
            if not vehicle:
                continue
            pos = item.get("position")
            if isinstance(pos, list) and len(pos) >= 3:
                try:
                    vehicle["node"].setPos(float(pos[0]), float(pos[1]), float(pos[2]))
                except Exception:
                    pass
            try:
                vehicle["node"].setH(float(item.get("heading", 0.0)))
            except Exception:
                pass
            vel = item.get("velocity")
            if isinstance(vel, list) and len(vel) >= 3:
                vehicle["velocity"] = Vec3(float(vel[0]), float(vel[1]), float(vel[2]))
            else:
                vehicle["velocity"] = Vec3(0, 0, 0)

        mounted_id = None
        mount_state = payload.get("mount_state")
        if isinstance(mount_state, dict):
            if bool(mount_state.get("is_mounted")):
                mounted_id = str(mount_state.get("vehicle_id", "")).strip()
        if not mounted_id:
            mounted_id = str(payload.get("mounted_vehicle_id", "")).strip()

        if mounted_id and mounted_id in self._vehicles_by_id:
            self.mounted_vehicle_id = mounted_id
            if player is not None:
                self._place_player_on_vehicle(player, self._vehicles_by_id[mounted_id])
                self._sync_char_state_with_actor(player)
        else:
            self.mounted_vehicle_id = None

    def get_interaction_hint(self, player) -> str:
        if not player or not getattr(player, "actor", None):
            return ""
        if self.is_mounted:
            vehicle = self.mounted_vehicle()
            if vehicle:
                return f"X: Dismount ({vehicle['kind']})"
            return "X: Dismount"

        player_pos = player.actor.getPos(self.app.render)
        vehicle, _ = self.find_nearest_vehicle(player_pos, radius=4.2)
        if not vehicle:
            return ""
        return f"X: Mount ({vehicle['kind']})"

    def handle_interact(self, player) -> bool:
        if self.is_mounted:
            return self.dismount(player)

        if not getattr(player, "actor", None):
            return False
        player_pos = player.actor.getPos(self.app.render)
        vehicle, _ = self.find_nearest_vehicle(player_pos, radius=4.2)
        if not vehicle:
            return False
        return self.mount(player, vehicle)

    def find_nearest_vehicle(self, point: Vec3, radius: float = 4.0) -> Tuple[Optional[Dict], float]:
        nearest = None
        nearest_dist = float(radius)
        for vehicle in self.vehicles:
            pos = vehicle["node"].getPos(self.app.render)
            dist = (pos - point).length()
            if dist <= nearest_dist:
                nearest = vehicle
                nearest_dist = dist
        return nearest, nearest_dist

    def mount(self, player, vehicle: Dict) -> bool:
        if not vehicle:
            return False
        if not getattr(player, "actor", None):
            return False

        self.mounted_vehicle_id = vehicle["id"]
        vehicle["velocity"] = Vec3(0, 0, 0)
        if hasattr(player, "_is_flying"):
            player._is_flying = False
        if hasattr(player, "_set_weapon_drawn"):
            player._set_weapon_drawn(False, reset_timer=True)
        self._place_player_on_vehicle(player, vehicle)
        self._sync_char_state_with_actor(player)
        logger.info(f"[VehicleManager] Mounted: {vehicle['kind']} ({vehicle['id']})")
        return True

    def dismount(self, player) -> bool:
        vehicle = self.mounted_vehicle()
        if not vehicle or not getattr(player, "actor", None):
            return False

        node = vehicle["node"]
        offset = vehicle.get("dismount_offset", Vec3(1.4, 0.0, 0.0))
        base = node.getPos(self.app.render)
        heading = math.radians(node.getH(self.app.render))

        # State-gated fail-safe: evaluate multiple side offsets to avoid bad dismount positions.
        candidates = [Vec3(offset), Vec3(offset.x, -offset.y, offset.z), Vec3(-offset.x * 0.8, offset.y, offset.z)]
        out_pos = None
        for cand in candidates:
            dx = (cand.x * math.cos(heading)) + (cand.y * math.sin(heading))
            dy = (-cand.x * math.sin(heading)) + (cand.y * math.cos(heading))
            p = Vec3(base.x + dx, base.y + dy, base.z + cand.z)
            if vehicle["kind"] != "ship":
                p.z = self._ground_height(p.x, p.y) + 0.08
            if self._is_valid_dismount_position(p, vehicle):
                out_pos = p
                break

        if out_pos is None:
            if vehicle["kind"] == "ship":
                return False
            out_pos = Vec3(base.x, base.y, self._ground_height(base.x, base.y) + 0.08)

        player.actor.setPos(out_pos)
        player.actor.setH(node.getH(self.app.render))
        self._sync_char_state_with_actor(player)

        vehicle["velocity"] = Vec3(0, 0, 0)
        self.mounted_vehicle_id = None
        logger.info(f"[VehicleManager] Dismounted: {vehicle['kind']} ({vehicle['id']})")
        return True

    def update_mounted(self, player, dt, mx, my, running, cam_yaw) -> bool:
        vehicle = self.mounted_vehicle()
        if not vehicle:
            return False

        dt = max(0.0, float(dt))
        node = vehicle["node"]
        move = self._camera_relative_move(mx, my, cam_yaw)
        if move.length_squared() > 1e-6:
            move.normalize()

        max_speed = float(vehicle["run_speed"] if running else vehicle["speed"])
        accel = float(vehicle.get("accel", 8.0))
        decel = float(vehicle.get("decel", 10.0))
        turn_rate = float(vehicle.get("turn_rate", 120.0))
        velocity = vehicle.get("velocity", Vec3(0, 0, 0))

        if move.length_squared() > 1e-6:
            target_velocity = move * max_speed
            blend = min(1.0, max(0.0, accel * dt))
            velocity = velocity + ((target_velocity - velocity) * blend)
        else:
            decay = max(0.0, 1.0 - min(1.0, decel * dt))
            velocity = velocity * decay

        current_pos = node.getPos(self.app.render)
        next_pos = current_pos + (velocity * dt)

        if vehicle["kind"] == "ship":
            if self._is_ship_navigable(next_pos.x, next_pos.y, vehicle):
                node.setPos(next_pos)
            else:
                velocity = velocity * 0.22
                node.setPos(current_pos + (velocity * dt))

            t = globalClock.getFrameTime()
            water_h = self._sample_water_height(node.getX(self.app.render), node.getY(self.app.render), vehicle)
            bob_amp = float(vehicle.get("wave_bob_amplitude", 0.12))
            bob_speed = float(vehicle.get("wave_bob_speed", 2.2))
            node.setZ(water_h + (math.sin((t * bob_speed) + float(vehicle.get("wave_phase", 0.0))) * bob_amp))
            node.setR(math.sin(t * 1.25) * 1.4)
            node.setP(math.cos(t * 1.06) * 1.1)
        else:
            node.setPos(next_pos)
            pos = node.getPos(self.app.render)
            node.setZ(self._ground_height(pos.x, pos.y) + vehicle["ground_offset"])
            node.setR(0.0)
            node.setP(0.0)

        flat_speed = math.sqrt((velocity.x * velocity.x) + (velocity.y * velocity.y))
        if flat_speed > 0.05:
            target_h = 180.0 - math.degrees(math.atan2(velocity.x, velocity.y))
            current_h = float(node.getH(self.app.render))
            delta_h = ((target_h - current_h + 180.0) % 360.0) - 180.0
            node.setH(self.app.render, current_h + max(-turn_rate * dt, min(turn_rate * dt, delta_h)))

        vehicle["velocity"] = velocity
        self._place_player_on_vehicle(player, vehicle)
        self._sync_char_state_with_actor(player)
        return flat_speed > 0.14

    def _spawn_entries_from_config(self) -> List[Dict]:
        data_mgr = getattr(self.app, "data_mgr", None)

        if data_mgr and hasattr(data_mgr, "get_world_layout"):
            layout = data_mgr.get_world_layout()
            if isinstance(layout, dict):
                entries = layout.get("vehicle_spawns", [])
                if isinstance(entries, list) and entries:
                    return [dict(item) for item in entries if isinstance(item, dict)]

        world_cfg = getattr(getattr(self.app, "data_mgr", None), "world_config", {})
        entries = world_cfg.get("vehicles", []) if isinstance(world_cfg, dict) else []
        if not isinstance(entries, list) or not entries:
            return [dict(e) for e in self.DEFAULT_SPAWNS]
        out = []
        for item in entries:
            if isinstance(item, dict):
                out.append(dict(item))
        return out if out else [dict(e) for e in self.DEFAULT_SPAWNS]

    def _spawn_vehicle_from_entry(self, entry: Dict, fallback_index=0) -> Optional[Dict]:
        kind = self._normalize_kind(entry.get("kind", ""))
        if kind not in {"horse", "carriage", "ship"}:
            return None

        vehicle_id = str(entry.get("id") or f"{kind}_{fallback_index+1}")
        pos = entry.get("pos", [0.0, 0.0])
        if not (isinstance(pos, list) and len(pos) >= 2):
            pos = [0.0, 0.0]
        x = float(pos[0])
        y = float(pos[1])
        heading = float(entry.get("heading", 0.0) or 0.0)

        if kind == "horse":
            vehicle = self._spawn_horse(vehicle_id, x, y)
        elif kind == "carriage":
            vehicle = self._spawn_carriage(vehicle_id, x, y)
        else:
            vehicle = self._spawn_ship(vehicle_id, x, y)

        vehicle["node"].setH(heading)
        self._apply_vehicle_tuning(vehicle, entry)
        return vehicle

    def _normalize_kind(self, kind):
        token = str(kind or "").strip().lower()
        if token == "boat":
            return "ship"
        return token

    def _coerce_offset(self, value, fallback):
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                return Vec3(float(value[0]), float(value[1]), float(value[2]))
            except Exception:
                return Vec3(fallback)
        if isinstance(value, Vec3):
            return Vec3(value)
        return Vec3(fallback)

    def _apply_vehicle_tuning(self, vehicle: Dict, entry: Dict):
        kind = vehicle.get("kind", "default")
        data_mgr = getattr(self.app, "data_mgr", None)
        get_param = getattr(data_mgr, "get_vehicle_param", None)
        get_cfg = getattr(data_mgr, "get_vehicle_config", None)
        kind_cfg = get_cfg(kind) if callable(get_cfg) else {}
        if not isinstance(kind_cfg, dict):
            kind_cfg = {}

        def pick(name, fallback):
            if isinstance(entry, dict) and name in entry:
                try:
                    return float(entry.get(name, fallback))
                except Exception:
                    return float(fallback)
            if name in kind_cfg:
                try:
                    return float(kind_cfg.get(name, fallback))
                except Exception:
                    return float(fallback)
            if callable(get_param):
                cfg = get_param(kind, name, fallback)
                try:
                    return float(cfg)
                except Exception:
                    return float(fallback)
            return float(fallback)

        # State-gating values are data-driven to avoid hardcoded behavior drift.
        vehicle["speed"] = pick("speed", vehicle.get("speed", 6.0))
        vehicle["run_speed"] = pick("run_speed", vehicle.get("run_speed", vehicle["speed"] * 1.5))
        vehicle["accel"] = pick("accel", 8.0)
        vehicle["decel"] = pick("decel", 10.0)
        vehicle["turn_rate"] = pick("turn_rate", 120.0)
        vehicle["velocity"] = Vec3(0, 0, 0)

        if "ground_offset" in kind_cfg or "ground_offset" in entry:
            vehicle["ground_offset"] = pick("ground_offset", vehicle.get("ground_offset", 0.0))

        mount_off = entry.get("mount_offset", kind_cfg.get("mount_offset"))
        dismount_off = entry.get("dismount_offset", kind_cfg.get("dismount_offset"))
        vehicle["mount_offset"] = self._coerce_offset(mount_off, vehicle.get("mount_offset", Vec3(0, 0, 1.0)))
        vehicle["dismount_offset"] = self._coerce_offset(dismount_off, vehicle.get("dismount_offset", Vec3(1.4, 0.0, 0.0)))

        if vehicle["kind"] == "ship":
            vehicle["water_level"] = pick("water_level", vehicle.get("water_level", -1.25))
            vehicle["wave_bob_amplitude"] = pick("wave_bob_amplitude", vehicle.get("wave_bob_amplitude", 0.12))
            vehicle["wave_bob_speed"] = pick("wave_bob_speed", vehicle.get("wave_bob_speed", 2.2))
            vehicle["wave_phase"] = float(entry.get("wave_phase", 0.0) or 0.0)
            nav_zone_id = str(entry.get("nav_zone_id", kind_cfg.get("nav_zone_id", "")) or "").strip()
            vehicle["nav_zone_id"] = nav_zone_id

    def _place_player_on_vehicle(self, player, vehicle):
        if not player or not getattr(player, "actor", None):
            return
        node = vehicle["node"]
        offset = vehicle.get("mount_offset", Vec3(0.0, 0.0, 1.0))
        wp = node.getPos(self.app.render)
        h = math.radians(node.getH(self.app.render))
        dx = (offset.x * math.cos(h)) + (offset.y * math.sin(h))
        dy = (-offset.x * math.sin(h)) + (offset.y * math.cos(h))
        player.actor.setPos(wp.x + dx, wp.y + dy, wp.z + offset.z)
        player.actor.setH(node.getH(self.app.render))

    def _sync_char_state_with_actor(self, player):
        cs = getattr(player, "cs", None)
        if not cs:
            return
        if hasattr(cs, "velocity"):
            cs.velocity.x = 0.0
            cs.velocity.y = 0.0
            cs.velocity.z = 0.0
        if hasattr(cs, "position"):
            p = player.actor.getPos(self.app.render)
            cs.position.x = p.x
            cs.position.y = p.y
            cs.position.z = p.z

    def _camera_relative_move(self, mx, my, cam_yaw):
        yaw_radians = math.radians(cam_yaw)
        dx = (mx * math.cos(yaw_radians)) + (my * math.sin(yaw_radians))
        dy = (-mx * math.sin(yaw_radians)) + (my * math.cos(yaw_radians))
        return Vec3(dx, dy, 0.0)

    def _load_navigation_zones(self):
        self._nav_zones = []
        data_mgr = getattr(self.app, "data_mgr", None)
        layout = data_mgr.get_world_layout() if data_mgr and hasattr(data_mgr, "get_world_layout") else {}
        zones = layout.get("navigation_zones", []) if isinstance(layout, dict) else []
        if not isinstance(zones, list):
            return
        for zone in zones:
            if isinstance(zone, dict):
                self._nav_zones.append(dict(zone))

    def _zone_allows_kind(self, zone, kind):
        kinds = zone.get("kinds", [])
        if not isinstance(kinds, list) or not kinds:
            return True
        token = self._normalize_kind(kind)
        return token in {self._normalize_kind(v) for v in kinds}

    def _distance_to_segment(self, px, py, ax, ay, bx, by):
        dx = bx - ax
        dy = by - ay
        ln_sq = (dx * dx) + (dy * dy)
        if ln_sq <= 1e-8:
            return math.sqrt(((px - ax) ** 2) + ((py - ay) ** 2))
        t = max(0.0, min(1.0, (((px - ax) * dx) + ((py - ay) * dy)) / ln_sq))
        qx = ax + (t * dx)
        qy = ay + (t * dy)
        return math.sqrt(((px - qx) ** 2) + ((py - qy) ** 2))

    def _point_in_nav_zone(self, x, y, zone):
        ztype = str(zone.get("type", "polygon") or "polygon").strip().lower()
        if ztype == "circle":
            center = zone.get("center", [])
            if not (isinstance(center, list) and len(center) >= 2):
                return False
            radius = float(zone.get("radius", 0.0) or 0.0)
            if radius <= 0.0:
                return False
            dx = x - float(center[0])
            dy = y - float(center[1])
            return ((dx * dx) + (dy * dy)) <= (radius * radius)

        if ztype == "corridor":
            points = zone.get("points", [])
            width = float(zone.get("width", 0.0) or 0.0)
            if not (isinstance(points, list) and len(points) >= 2 and width > 0.0):
                return False
            for idx in range(len(points) - 1):
                a = points[idx]
                b = points[idx + 1]
                if not (isinstance(a, list) and isinstance(b, list) and len(a) >= 2 and len(b) >= 2):
                    continue
                dist = self._distance_to_segment(x, y, float(a[0]), float(a[1]), float(b[0]), float(b[1]))
                if dist <= width:
                    return True
            return False

        points = zone.get("points", [])
        if not (isinstance(points, list) and len(points) >= 3):
            return False
        inside = False
        j = len(points) - 1
        for i in range(len(points)):
            pi = points[i]
            pj = points[j]
            if not (isinstance(pi, list) and isinstance(pj, list) and len(pi) >= 2 and len(pj) >= 2):
                j = i
                continue
            xi, yi = float(pi[0]), float(pi[1])
            xj, yj = float(pj[0]), float(pj[1])
            hit = ((yi > y) != (yj > y)) and (x < ((xj - xi) * (y - yi) / max(1e-8, (yj - yi)) + xi))
            if hit:
                inside = not inside
            j = i
        return inside

    def _is_ship_navigable(self, x, y, vehicle=None):
        if self._nav_zones:
            vehicle_zone_id = ""
            if isinstance(vehicle, dict):
                vehicle_zone_id = str(vehicle.get("nav_zone_id", "") or "").strip()
            for zone in self._nav_zones:
                if not self._zone_allows_kind(zone, "ship"):
                    continue
                if vehicle_zone_id and str(zone.get("id", "") or "").strip() != vehicle_zone_id:
                    continue
                if self._point_in_nav_zone(x, y, zone):
                    return True
            if vehicle_zone_id:
                return False

        # Backward-compatible fallback for older maps without explicit nav zones.
        world = getattr(self.app, "world", None)
        if not world:
            return True
        if y < -48.0:
            return True
        if hasattr(world, "_distance_to_river"):
            try:
                if float(world._distance_to_river(x, y)) <= 7.5:
                    return True
            except Exception:
                pass
        try:
            h = float(world._th(x, y))
            if h <= 0.35:
                return True
        except Exception:
            pass
        return False

    def _sample_water_height(self, x, y, vehicle):
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "sample_water_height"):
            try:
                return float(world.sample_water_height(float(x), float(y)))
            except Exception:
                pass
        return float(vehicle.get("water_level", -1.25))

    def _is_valid_dismount_position(self, pos, vehicle):
        if vehicle.get("kind") == "ship":
            # Ship dismount is allowed only near shore/riverbanks.
            h = self._ground_height(pos.x, pos.y)
            return h >= -0.15
        return True

    def _spawn_horse(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.55
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        body = root.attachNewNode(mk_box(f"{vehicle_id}_body", 1.7, 0.7, 0.75))
        body.setColor(LColor(0.45, 0.29, 0.17, 1.0))

        neck = root.attachNewNode(mk_box(f"{vehicle_id}_neck", 0.45, 0.35, 0.55))
        neck.setPos(0.92, 0.0, 0.32)
        neck.setColor(LColor(0.43, 0.27, 0.15, 1.0))

        head = root.attachNewNode(mk_box(f"{vehicle_id}_head", 0.42, 0.28, 0.32))
        head.setPos(1.20, 0.0, 0.38)
        head.setColor(LColor(0.40, 0.24, 0.13, 1.0))

        tail = root.attachNewNode(mk_cone(f"{vehicle_id}_tail", 0.10, 0.55, 10))
        tail.setPos(-0.95, 0.0, 0.22)
        tail.setHpr(0, -70, 0)
        tail.setColor(LColor(0.20, 0.15, 0.10, 1.0))

        legs = [(-0.58, -0.22), (-0.58, 0.22), (0.52, -0.22), (0.52, 0.22)]
        for idx, (lx, ly) in enumerate(legs):
            leg = root.attachNewNode(mk_cyl(f"{vehicle_id}_leg_{idx}", 0.08, 0.8, 8))
            leg.setPos(lx, ly, -0.30)
            leg.setColor(LColor(0.24, 0.18, 0.11, 1.0))

        return {
            "id": vehicle_id,
            "kind": "horse",
            "node": root,
            "speed": 8.0,
            "run_speed": 13.0,
            "ground_offset": 0.55,
            "mount_offset": Vec3(0.0, 0.0, 0.95),
            "dismount_offset": Vec3(1.2, -0.6, 0.0),
        }

    def _spawn_carriage(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.65
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        base = root.attachNewNode(mk_box(f"{vehicle_id}_base", 2.7, 1.35, 0.62))
        base.setColor(LColor(0.33, 0.22, 0.12, 1.0))

        cabin = root.attachNewNode(mk_box(f"{vehicle_id}_cabin", 1.55, 1.05, 1.0))
        cabin.setPos(0.0, 0.0, 0.72)
        cabin.setColor(LColor(0.42, 0.29, 0.16, 1.0))

        roof = root.attachNewNode(mk_box(f"{vehicle_id}_roof", 1.75, 1.20, 0.25))
        roof.setPos(0.0, 0.0, 1.36)
        roof.setColor(LColor(0.18, 0.12, 0.08, 1.0))

        wheels = [(-1.0, -0.72), (-1.0, 0.72), (1.0, -0.72), (1.0, 0.72)]
        for idx, (wx, wy) in enumerate(wheels):
            wheel = root.attachNewNode(mk_cyl(f"{vehicle_id}_wheel_{idx}", 0.30, 0.22, 12))
            wheel.setPos(wx, wy, -0.35)
            wheel.setR(90)
            wheel.setColor(LColor(0.14, 0.10, 0.08, 1.0))

        return {
            "id": vehicle_id,
            "kind": "carriage",
            "node": root,
            "speed": 6.0,
            "run_speed": 9.5,
            "ground_offset": 0.65,
            "mount_offset": Vec3(0.0, 0.0, 1.08),
            "dismount_offset": Vec3(1.8, -0.8, 0.0),
        }

    def _spawn_ship(self, vehicle_id, x, y):
        water_level = -1.25
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, water_level)

        hull = root.attachNewNode(mk_box(f"{vehicle_id}_hull", 4.1, 1.3, 0.78))
        hull.setColor(LColor(0.30, 0.20, 0.12, 1.0))

        deck = root.attachNewNode(mk_box(f"{vehicle_id}_deck", 2.9, 1.02, 0.14))
        deck.setPos(0.0, 0.0, 0.46)
        deck.setColor(LColor(0.48, 0.35, 0.22, 1.0))

        mast = root.attachNewNode(mk_cyl(f"{vehicle_id}_mast", 0.08, 2.8, 10))
        mast.setPos(0.25, 0.0, 1.45)
        mast.setColor(LColor(0.42, 0.31, 0.19, 1.0))

        sail = root.attachNewNode(mk_box(f"{vehicle_id}_sail", 0.06, 1.15, 1.48))
        sail.setPos(0.42, 0.0, 1.58)
        sail.setColor(LColor(0.86, 0.84, 0.77, 0.96))

        return {
            "id": vehicle_id,
            "kind": "ship",
            "node": root,
            "speed": 7.0,
            "run_speed": 11.5,
            "water_level": water_level,
            "ground_offset": 0.0,
            "mount_offset": Vec3(0.0, 0.0, 0.86),
            "dismount_offset": Vec3(1.6, 0.0, 0.15),
            "wave_bob_amplitude": 0.12,
            "wave_bob_speed": 2.2,
            "nav_zone_id": "",
        }

    def _ground_height(self, x, y):
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "_th"):
            try:
                return float(world._th(x, y))
            except Exception:
                pass
        return 0.0
