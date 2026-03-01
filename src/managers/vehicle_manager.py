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
        {"id": "boat_1", "kind": "boat", "pos": [0.0, -77.0], "heading": 180.0},
    ]

    def __init__(self, app):
        self.app = app
        self.vehicles: List[Dict] = []
        self._vehicles_by_id: Dict[str, Dict] = {}
        self.mounted_vehicle_id: Optional[str] = None
        self._bootstrapped = False

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

        entries = self._spawn_entries_from_config()
        for idx, entry in enumerate(entries):
            vehicle = self._spawn_vehicle_from_entry(entry, fallback_index=idx)
            if not vehicle:
                continue
            self.vehicles.append(vehicle)
            self._vehicles_by_id[vehicle["id"]] = vehicle

        self._bootstrapped = True
        logger.info(f"[VehicleManager] Spawned transports: {len(self.vehicles)}")

    def export_state(self) -> Dict:
        vehicles = []
        for vehicle in self.vehicles:
            node = vehicle["node"]
            pos = node.getPos(self.app.render)
            vel = vehicle.get("velocity", Vec3(0, 0, 0))
            vehicles.append(
                {
                    "id": vehicle["id"],
                    "kind": vehicle["kind"],
                    "position": [float(pos.x), float(pos.y), float(pos.z)],
                    "heading": float(node.getH(self.app.render)),
                    "velocity": [float(vel.x), float(vel.y), float(vel.z)],
                }
            )
        return {
            "mounted_vehicle_id": self.mounted_vehicle_id,
            "vehicles": vehicles,
        }

    def import_state(self, payload, player=None):
        if not isinstance(payload, dict):
            return

        for item in payload.get("vehicles", []) if isinstance(payload.get("vehicles"), list) else []:
            if not isinstance(item, dict):
                continue
            vehicle = self._vehicles_by_id.get(str(item.get("id", "")))
            if not vehicle:
                continue
            pos = item.get("position")
            if isinstance(pos, list) and len(pos) >= 3:
                vehicle["node"].setPos(float(pos[0]), float(pos[1]), float(pos[2]))
            try:
                vehicle["node"].setH(float(item.get("heading", 0.0)))
            except Exception:
                pass
            vel = item.get("velocity")
            if isinstance(vel, list) and len(vel) >= 3:
                vehicle["velocity"] = Vec3(float(vel[0]), float(vel[1]), float(vel[2]))
            else:
                vehicle["velocity"] = Vec3(0, 0, 0)

        mounted_id = payload.get("mounted_vehicle_id")
        if isinstance(mounted_id, str) and mounted_id in self._vehicles_by_id:
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
        if not vehicle:
            return False

        node = vehicle["node"]
        offset = vehicle.get("dismount_offset", Vec3(1.4, 0.0, 0.0))
        wp = node.getPos(self.app.render)
        h = math.radians(node.getH(self.app.render))
        dx = (offset.x * math.cos(h)) + (offset.y * math.sin(h))
        dy = (-offset.x * math.sin(h)) + (offset.y * math.cos(h))
        out_pos = Vec3(wp.x + dx, wp.y + dy, wp.z + offset.z)
        if vehicle["kind"] != "boat":
            out_pos.z = self._ground_height(out_pos.x, out_pos.y) + 0.08

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

        node = vehicle["node"]
        move = self._camera_relative_move(mx, my, cam_yaw)
        if move.length_squared() > 1e-6:
            move.normalize()

        max_speed = float(vehicle["run_speed"] if running else vehicle["speed"])
        accel = float(vehicle.get("accel", 8.0))
        decel = float(vehicle.get("decel", 10.0))
        velocity = vehicle.get("velocity", Vec3(0, 0, 0))

        if move.length_squared() > 1e-6:
            target_velocity = move * max_speed
            blend = min(1.0, max(0.0, accel * max(0.0, dt)))
            velocity = velocity + ((target_velocity - velocity) * blend)
        else:
            decay = max(0.0, 1.0 - min(1.0, decel * max(0.0, dt)))
            velocity = velocity * decay

        current_pos = node.getPos(self.app.render)
        next_pos = current_pos + (velocity * max(0.0, dt))

        if vehicle["kind"] == "boat":
            if self._is_boat_navigable(next_pos.x, next_pos.y):
                node.setPos(next_pos)
            else:
                velocity = velocity * 0.25
                node.setPos(current_pos + (velocity * max(0.0, dt)))
            t = globalClock.getFrameTime()
            node.setZ(vehicle["water_level"] + math.sin(t * 2.2) * 0.10)
        else:
            node.setPos(next_pos)
            pos = node.getPos(self.app.render)
            node.setZ(self._ground_height(pos.x, pos.y) + vehicle["ground_offset"])

        flat_speed = math.sqrt((velocity.x * velocity.x) + (velocity.y * velocity.y))
        if flat_speed > 0.05:
            node.setH(180.0 - math.degrees(math.atan2(velocity.x, velocity.y)))

        vehicle["velocity"] = velocity
        self._place_player_on_vehicle(player, vehicle)
        self._sync_char_state_with_actor(player)
        return True

    def _spawn_entries_from_config(self) -> List[Dict]:
        world_cfg = getattr(self.app.data_mgr, "world_config", {})
        entries = world_cfg.get("vehicles", []) if isinstance(world_cfg, dict) else []
        if not isinstance(entries, list) or not entries:
            return [dict(e) for e in self.DEFAULT_SPAWNS]
        out = []
        for item in entries:
            if isinstance(item, dict):
                out.append(dict(item))
        return out if out else [dict(e) for e in self.DEFAULT_SPAWNS]

    def _spawn_vehicle_from_entry(self, entry: Dict, fallback_index=0) -> Optional[Dict]:
        kind = str(entry.get("kind", "")).strip().lower()
        if kind not in {"horse", "carriage", "boat"}:
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
            vehicle = self._spawn_boat(vehicle_id, x, y)

        vehicle["node"].setH(heading)
        self._apply_vehicle_tuning(vehicle, entry)
        return vehicle

    def _apply_vehicle_tuning(self, vehicle: Dict, entry: Dict):
        kind = vehicle.get("kind", "default")
        get_param = getattr(self.app.data_mgr, "get_vehicle_param", None)

        def pick(name, fallback):
            if isinstance(entry, dict) and name in entry:
                try:
                    return float(entry.get(name, fallback))
                except Exception:
                    return float(fallback)
            if callable(get_param):
                cfg = get_param(kind, name, fallback)
                try:
                    return float(cfg)
                except Exception:
                    return float(fallback)
            return float(fallback)

        vehicle["speed"] = pick("speed", vehicle.get("speed", 6.0))
        vehicle["run_speed"] = pick("run_speed", vehicle.get("run_speed", vehicle["speed"] * 1.5))
        vehicle["accel"] = pick("accel", 8.0)
        vehicle["decel"] = pick("decel", 10.0)
        if vehicle["kind"] == "boat":
            vehicle["water_level"] = pick("water_level", vehicle.get("water_level", -1.25))
        vehicle["velocity"] = Vec3(0, 0, 0)

    def _place_player_on_vehicle(self, player, vehicle):
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

    def _is_boat_navigable(self, x, y):
        world = getattr(self.app, "world", None)
        if not world:
            return True

        if y < -48.0:
            return True

        if hasattr(world, "_distance_to_river"):
            try:
                if float(world._distance_to_river(x, y)) <= 6.5:
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

    def _spawn_boat(self, vehicle_id, x, y):
        water_level = -1.25
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, water_level)

        hull = root.attachNewNode(mk_box(f"{vehicle_id}_hull", 3.8, 1.15, 0.72))
        hull.setColor(LColor(0.30, 0.20, 0.12, 1.0))

        deck = root.attachNewNode(mk_box(f"{vehicle_id}_deck", 2.8, 0.95, 0.14))
        deck.setPos(0.0, 0.0, 0.43)
        deck.setColor(LColor(0.48, 0.35, 0.22, 1.0))

        mast = root.attachNewNode(mk_cyl(f"{vehicle_id}_mast", 0.08, 2.6, 10))
        mast.setPos(0.25, 0.0, 1.35)
        mast.setColor(LColor(0.42, 0.31, 0.19, 1.0))

        sail = root.attachNewNode(mk_box(f"{vehicle_id}_sail", 0.06, 1.05, 1.40))
        sail.setPos(0.42, 0.0, 1.45)
        sail.setColor(LColor(0.85, 0.83, 0.76, 0.96))

        return {
            "id": vehicle_id,
            "kind": "boat",
            "node": root,
            "speed": 7.0,
            "run_speed": 11.5,
            "water_level": water_level,
            "ground_offset": 0.0,
            "mount_offset": Vec3(0.0, 0.0, 0.86),
            "dismount_offset": Vec3(1.6, 0.0, 0.15),
        }

    def _ground_height(self, x, y):
        world = getattr(self.app, "world", None)
        if world and hasattr(world, "_th"):
            try:
                return float(world._th(x, y))
            except Exception:
                pass
        return 0.0
