import math
from typing import Dict, List, Optional, Tuple

from utils.core_runtime import gc, HAS_CORE
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import LColor, Vec3

from render.model_visuals import ensure_model_visual_defaults
from utils.logger import logger
from world.sharuan_world import mk_box, mk_cone, mk_cyl, mk_sphere


class VehicleManager:
    """Mountable transport system with data-driven spawns and tuning."""

    DEFAULT_SPAWNS = [
        {"id": "horse_1", "kind": "horse", "pos": [9.0, 6.0], "heading": 25.0},
        {"id": "wolf_1", "kind": "wolf", "pos": [13.0, 9.0], "heading": 205.0},
        {"id": "stag_1", "kind": "stag", "pos": [16.0, 12.0], "heading": 154.0},
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
            probe = getattr(self.app, "_debug_probe_runtime_node", None)
            if callable(probe):
                probe(
                    f"vehicle_spawn:{vehicle['id']}",
                    vehicle.get("node"),
                    reference=getattr(self.app, "render", None),
                )

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
                return f"X: Dismount ({self._display_kind_name(vehicle.get('kind', ''))})"
            return "X: Dismount"

        player_pos = player.actor.getPos(self.app.render)
        vehicle, _ = self.find_nearest_vehicle(player_pos, radius=4.2)
        if not vehicle:
            return ""
        return f"X: Mount ({self._display_kind_name(vehicle.get('kind', ''))})"

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

    def _default_vehicle_profile(self, kind):
        token = self._normalize_kind(kind)
        if token == "wolf":
            return {
                "speed": 9.5,
                "run_speed": 15.2,
                "ground_offset": 0.56,
                "mount_offset": Vec3(0.0, 0.0, 0.92),
                "dismount_offset": Vec3(1.2, -0.7, 0.0),
            }
        if token == "stag":
            return {
                "speed": 9.0,
                "run_speed": 14.4,
                "ground_offset": 0.64,
                "mount_offset": Vec3(0.0, 0.0, 0.98),
                "dismount_offset": Vec3(1.3, -0.65, 0.0),
            }
        if token == "carriage":
            return {
                "speed": 6.0,
                "run_speed": 9.5,
                "ground_offset": 0.74,
                "mount_offset": Vec3(0.0, 0.0, 1.08),
                "dismount_offset": Vec3(1.8, -0.8, 0.0),
            }
        if token == "ship":
            return {
                "speed": 7.0,
                "run_speed": 11.5,
                "water_level": -1.25,
                "ground_offset": 0.0,
                "mount_offset": Vec3(0.0, 0.0, 0.86),
                "dismount_offset": Vec3(1.6, 0.0, 0.15),
                "wave_bob_amplitude": 0.12,
                "wave_bob_speed": 2.2,
                "nav_zone_id": "",
            }
        return {
            "speed": 8.0,
            "run_speed": 13.0,
            "ground_offset": 0.62,
            "mount_offset": Vec3(0.0, 0.0, 0.95),
            "dismount_offset": Vec3(1.2, -0.6, 0.0),
        }

    def _spawn_vehicle_from_model(self, kind, vehicle_id, x, y, entry):
        data_mgr = getattr(self.app, "data_mgr", None)
        get_cfg = getattr(data_mgr, "get_vehicle_config", None)
        kind_cfg = get_cfg(kind) if callable(get_cfg) else {}
        if not isinstance(kind_cfg, dict):
            kind_cfg = {}

        model_path = str(entry.get("model", kind_cfg.get("model", "")) or "").strip()
        if not model_path:
            return None

        loader = getattr(self.app, "loader", None)
        render = getattr(self.app, "render", None)
        if not loader or not render:
            return None

        profile = self._default_vehicle_profile(kind)
        if kind == "ship":
            z = float(entry.get("water_level", kind_cfg.get("water_level", profile.get("water_level", -1.25))) or -1.25)
        else:
            z = self._ground_height(x, y) + float(profile.get("ground_offset", 0.6) or 0.6)
        root = render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        try:
            model_np = loader.loadModel(model_path)
        except Exception as exc:
            logger.warning(f"[VehicleManager] Failed to load vehicle model '{model_path}' for {vehicle_id}: {exc}")
            root.removeNode()
            return None
        if not model_np or model_np.isEmpty():
            root.removeNode()
            return None
        model_np.reparentTo(root)

        model_offset = self._coerce_offset(
            entry.get("model_offset", kind_cfg.get("model_offset")),
            Vec3(0.0, 0.0, 0.0),
        )
        model_np.setPos(model_offset)

        model_hpr = entry.get("model_hpr", kind_cfg.get("model_hpr"))
        if isinstance(model_hpr, (list, tuple)) and len(model_hpr) >= 3:
            try:
                model_np.setHpr(float(model_hpr[0]), float(model_hpr[1]), float(model_hpr[2]))
            except Exception:
                pass

        scale_payload = entry.get("model_scale", kind_cfg.get("model_scale", 1.0))
        if isinstance(scale_payload, (list, tuple)) and len(scale_payload) >= 3:
            try:
                model_np.setScale(float(scale_payload[0]), float(scale_payload[1]), float(scale_payload[2]))
            except Exception:
                model_np.setScale(1.0)
        else:
            try:
                model_np.setScale(float(scale_payload))
            except Exception:
                model_np.setScale(1.0)

        self._apply_vehicle_visual_defaults(model_np, debug_label=f"vehicle_model:{vehicle_id}")

        out = {
            "id": vehicle_id,
            "kind": kind,
            "node": root,
            "speed": float(profile.get("speed", 8.0)),
            "run_speed": float(profile.get("run_speed", 13.0)),
            "ground_offset": float(profile.get("ground_offset", 0.62)),
            "mount_offset": Vec3(profile.get("mount_offset", Vec3(0.0, 0.0, 0.95))),
            "dismount_offset": Vec3(profile.get("dismount_offset", Vec3(1.2, -0.6, 0.0))),
        }
        if kind == "ship":
            out["water_level"] = float(profile.get("water_level", -1.25))
            out["wave_bob_amplitude"] = float(profile.get("wave_bob_amplitude", 0.12))
            out["wave_bob_speed"] = float(profile.get("wave_bob_speed", 2.2))
            out["nav_zone_id"] = str(profile.get("nav_zone_id", "") or "")
        return out

    def _spawn_vehicle_from_entry(self, entry: Dict, fallback_index=0) -> Optional[Dict]:
        kind = self._normalize_kind(entry.get("kind", ""))
        if kind not in {"horse", "wolf", "stag", "carriage", "ship"}:
            return None

        vehicle_id = str(entry.get("id") or f"{kind}_{fallback_index+1}")
        pos = entry.get("pos", [0.0, 0.0])
        if not (isinstance(pos, list) and len(pos) >= 2):
            pos = [0.0, 0.0]
        x = float(pos[0])
        y = float(pos[1])
        heading = float(entry.get("heading", 0.0) or 0.0)

        vehicle = self._spawn_vehicle_from_model(kind, vehicle_id, x, y, entry)
        if vehicle is None:
            if kind == "horse":
                vehicle = self._spawn_horse(vehicle_id, x, y)
            elif kind == "wolf":
                vehicle = self._spawn_wolf(vehicle_id, x, y)
            elif kind == "stag":
                vehicle = self._spawn_stag(vehicle_id, x, y)
            elif kind == "carriage":
                vehicle = self._spawn_carriage(vehicle_id, x, y)
            else:
                vehicle = self._spawn_ship(vehicle_id, x, y)

        vehicle["node"].setH(heading)
        self._apply_vehicle_tuning(vehicle, entry)
        self._apply_vehicle_textures(vehicle["node"])
        self._apply_vehicle_visual_defaults(vehicle["node"], debug_label=f"vehicle:{vehicle_id}")
        return vehicle

    def _apply_vehicle_textures(self, node):
        if not node or node.isEmpty():
            return
        world = getattr(self.app, "world", None)
        tx = getattr(world, "tx", {}) if world else {}
        bark = tx.get("bark", {}) if isinstance(tx.get("bark"), dict) else {}
        roof = tx.get("roof", {}) if isinstance(tx.get("roof"), dict) else {}
        dirt = tx.get("dirt", {}) if isinstance(tx.get("dirt"), dict) else {}
        bark_tex = bark.get("albedo")
        cloth_tex = roof.get("albedo") or dirt.get("albedo")

        if not bark_tex and not cloth_tex:
            return

        for geom_np in node.findAllMatches("**/+GeomNode"):
            try:
                name = str(geom_np.getName() or "").strip().lower()
            except Exception:
                name = ""
            tex = cloth_tex if "sail" in name else bark_tex
            if tex:
                try:
                    geom_np.setTexture(tex, 1)
                except Exception:
                    pass

    def _apply_vehicle_visual_defaults(self, node, debug_label):
        if not node or node.isEmpty():
            return
        ensure_model_visual_defaults(
            node,
            apply_skin=False,
            force_two_sided=True,
            debug_label=debug_label,
        )
        # Python-only mode: avoid dark fallback from heavy shader pipeline.
        if not HAS_CORE:
            try:
                node.setShaderOff(1002)
            except Exception:
                pass
            try:
                node.setColorScale(1.0, 1.0, 1.0, 1.0)
            except Exception:
                pass

    def _normalize_kind(self, kind):
        token = str(kind or "").strip().lower()
        aliases = {
            "boat": "ship",
            "skiff": "ship",
            "sloop": "ship",
            "pony": "horse",
            "mare": "horse",
            "direwolf": "wolf",
            "dire_wolf": "wolf",
            "warg": "wolf",
            "deer": "stag",
            "elk": "stag",
            "reindeer": "stag",
        }
        return aliases.get(token, token)

    def _display_kind_name(self, kind):
        token = self._normalize_kind(kind)
        labels = {
            "horse": "Horse",
            "wolf": "Dire Wolf",
            "stag": "Stag",
            "carriage": "Carriage",
            "ship": "Ship",
        }
        if token in labels:
            return labels[token]
        return str(token).replace("_", " ").title()

    def _vehicle_visual_palette(self, kind):
        token = self._normalize_kind(kind)
        if token == "wolf":
            return {
                "body": (0.28, 0.30, 0.34, 1.0),
                "body_dark": (0.14, 0.16, 0.20, 1.0),
                "body_light": (0.48, 0.50, 0.54, 1.0),
                "leather": (0.18, 0.14, 0.12, 1.0),
                "cloth": (0.24, 0.34, 0.42, 1.0),
                "metal": (0.62, 0.66, 0.72, 1.0),
                "accent": (0.44, 0.62, 0.78, 1.0),
                "glow": (0.54, 0.72, 0.96, 1.0),
            }
        if token == "stag":
            return {
                "body": (0.48, 0.33, 0.22, 1.0),
                "body_dark": (0.22, 0.16, 0.10, 1.0),
                "body_light": (0.68, 0.58, 0.46, 1.0),
                "leather": (0.24, 0.17, 0.10, 1.0),
                "cloth": (0.22, 0.32, 0.22, 1.0),
                "metal": (0.76, 0.71, 0.58, 1.0),
                "accent": (0.58, 0.74, 0.46, 1.0),
                "glow": (0.78, 0.86, 0.60, 1.0),
            }
        if token == "carriage":
            return {
                "body": (0.36, 0.24, 0.16, 1.0),
                "body_dark": (0.22, 0.15, 0.10, 1.0),
                "body_light": (0.50, 0.37, 0.24, 1.0),
                "leather": (0.18, 0.10, 0.10, 1.0),
                "cloth": (0.44, 0.16, 0.14, 1.0),
                "metal": (0.70, 0.62, 0.46, 1.0),
                "accent": (0.82, 0.66, 0.30, 1.0),
                "glow": (0.98, 0.78, 0.44, 1.0),
            }
        if token == "ship":
            return {
                "body": (0.30, 0.21, 0.14, 1.0),
                "body_dark": (0.19, 0.14, 0.10, 1.0),
                "body_light": (0.46, 0.34, 0.23, 1.0),
                "leather": (0.22, 0.17, 0.13, 1.0),
                "cloth": (0.86, 0.84, 0.78, 0.96),
                "metal": (0.66, 0.58, 0.44, 1.0),
                "accent": (0.22, 0.34, 0.48, 1.0),
                "glow": (0.96, 0.82, 0.52, 1.0),
            }
        if token == "horse":
            return {
                "body": (0.46, 0.30, 0.18, 1.0),
                "body_dark": (0.24, 0.17, 0.11, 1.0),
                "body_light": (0.64, 0.50, 0.34, 1.0),
                "leather": (0.27, 0.19, 0.12, 1.0),
                "cloth": (0.58, 0.20, 0.18, 1.0),
                "metal": (0.72, 0.70, 0.66, 1.0),
                "accent": (0.88, 0.68, 0.36, 1.0),
                "glow": (0.96, 0.82, 0.54, 1.0),
            }
        return {
            "body": (0.46, 0.30, 0.18, 1.0),
            "body_dark": (0.24, 0.17, 0.11, 1.0),
            "body_light": (0.64, 0.50, 0.34, 1.0),
            "leather": (0.27, 0.19, 0.12, 1.0),
            "cloth": (0.58, 0.20, 0.18, 1.0),
            "metal": (0.72, 0.70, 0.66, 1.0),
            "accent": (0.88, 0.68, 0.36, 1.0),
            "glow": (0.96, 0.82, 0.54, 1.0),
        }

    def _palette_lcolor(self, palette, key, fallback=(1.0, 1.0, 1.0, 1.0)):
        raw = palette.get(key, fallback) if isinstance(palette, dict) else fallback
        if not isinstance(raw, (list, tuple)) or len(raw) < 4:
            raw = fallback
        return LColor(float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))

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

    def _attach_colored_geom(self, parent, geom, color, pos=(0.0, 0.0, 0.0), hpr=(0.0, 0.0, 0.0), scale=None):
        node = parent.attachNewNode(geom)
        node.setPos(float(pos[0]), float(pos[1]), float(pos[2]))
        node.setHpr(float(hpr[0]), float(hpr[1]), float(hpr[2]))
        if isinstance(scale, (list, tuple)) and len(scale) >= 3:
            node.setScale(float(scale[0]), float(scale[1]), float(scale[2]))
        elif isinstance(scale, (int, float)):
            node.setScale(float(scale))
        node.setColor(color)
        return node

    def _spawn_horse(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.62
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        palette = self._vehicle_visual_palette("horse")
        coat = self._palette_lcolor(palette, "body")
        coat_dark = self._palette_lcolor(palette, "body_dark")
        coat_light = self._palette_lcolor(palette, "body_light")
        leather = self._palette_lcolor(palette, "leather")
        cloth = self._palette_lcolor(palette, "cloth")
        metal = self._palette_lcolor(palette, "metal")
        accent = self._palette_lcolor(palette, "accent")

        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_body", 0.56, 12, 16),
            coat,
            pos=(0.00, 0.00, 0.36),
            scale=(1.65, 0.82, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_chest", 0.32, 10, 14),
            coat,
            pos=(0.78, 0.00, 0.42),
            scale=(1.00, 0.92, 1.12),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_neck", 0.22, 10, 14),
            coat,
            pos=(1.00, 0.00, 0.74),
            hpr=(0.0, -18.0, 0.0),
            scale=(0.88, 0.62, 1.34),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_head", 0.26, 10, 14),
            coat,
            pos=(1.30, 0.00, 0.95),
            scale=(1.18, 0.74, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_muzzle", 0.13, 8, 12),
            coat,
            pos=(1.54, 0.00, 0.88),
            scale=(1.26, 0.62, 0.56),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_blaze", 0.06, 0.18, 0.24),
            coat_light,
            pos=(1.36, 0.0, 0.96),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_l", 0.05, 0.14, 9),
            coat_dark,
            pos=(1.22, 0.11, 1.16),
            hpr=(0.0, 18.0, 6.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_r", 0.05, 0.14, 9),
            coat_dark,
            pos=(1.22, -0.11, 1.16),
            hpr=(0.0, 18.0, -6.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_tail", 0.09, 0.66, 12),
            coat_dark,
            pos=(-1.06, 0.00, 0.56),
            hpr=(0.0, -65.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_mane", 0.18, 0.08, 0.76),
            coat_dark,
            pos=(1.00, 0.0, 0.96),
            hpr=(0.0, -24.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle", 0.62, 0.52, 0.13),
            leather,
            pos=(0.08, 0.00, 0.88),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle_pad", 0.76, 0.64, 0.06),
            cloth,
            pos=(0.08, 0.00, 0.79),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_breaststrap", 0.14, 0.76, 0.06),
            leather,
            pos=(0.74, 0.0, 0.70),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_bridle_band", 0.16, 0.04, 0.28),
            leather,
            pos=(1.42, 0.0, 0.94),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_nose_guard", 0.10, 0.20, 0.12),
            accent,
            pos=(1.56, 0.0, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_bedroll", 0.18, 0.52, 0.12),
            accent,
            pos=(-0.18, 0.0, 0.98),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_flank_cloth", 0.82, 0.08, 0.46),
            cloth,
            pos=(0.06, 0.0, 0.64),
        )

        legs = [(-0.58, -0.22), (-0.58, 0.22), (0.52, -0.22), (0.52, 0.22)]
        for idx, (lx, ly) in enumerate(legs):
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_leg_{idx}", 0.075, 0.82, 12),
                LColor(0.28, 0.20, 0.12, 1.0),
                pos=(lx, ly, -0.18),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_hoof_{idx}", 0.09, 8, 10),
                LColor(0.12, 0.09, 0.08, 1.0),
                pos=(lx, ly, -0.60),
                scale=(1.08, 1.08, 0.56),
            )

        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_stirrup_{'l' if side < 0 else 'r'}", 0.015, 0.28, 8),
                metal,
                pos=(0.02, 0.22 * side, 0.56),
            )
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_rein_{'l' if side < 0 else 'r'}", 0.010, 0.62, 8),
                leather,
                pos=(1.08, 0.12 * side, 0.90),
                hpr=(0.0, -58.0, 8.0 * side),
            )
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_flank_guard_{'l' if side < 0 else 'r'}", 0.52, 0.06, 0.34),
                accent,
                pos=(0.00, 0.32 * side, 0.68),
            )

        return {
            "id": vehicle_id,
            "kind": "horse",
            "node": root,
            "speed": 8.0,
            "run_speed": 13.0,
            "ground_offset": 0.62,
            "mount_offset": Vec3(0.0, 0.0, 0.95),
            "dismount_offset": Vec3(1.2, -0.6, 0.0),
        }

    def _spawn_wolf(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.56
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        palette = self._vehicle_visual_palette("wolf")
        fur_mid = self._palette_lcolor(palette, "body")
        fur_dark = self._palette_lcolor(palette, "body_dark")
        fur_light = self._palette_lcolor(palette, "body_light")
        leather = self._palette_lcolor(palette, "leather")
        cloth = self._palette_lcolor(palette, "cloth")
        metal = self._palette_lcolor(palette, "metal")
        accent = self._palette_lcolor(palette, "accent")

        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_body", 0.54, 12, 16),
            fur_mid,
            pos=(0.00, 0.00, 0.34),
            scale=(1.86, 0.76, 0.82),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_chest", 0.30, 10, 14),
            fur_light,
            pos=(0.72, 0.00, 0.38),
            scale=(1.14, 0.84, 1.02),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_neck", 0.22, 10, 14),
            fur_mid,
            pos=(0.92, 0.00, 0.64),
            hpr=(0.0, -14.0, 0.0),
            scale=(0.92, 0.62, 1.20),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_head", 0.24, 10, 14),
            fur_dark,
            pos=(1.20, 0.00, 0.82),
            scale=(1.14, 0.70, 0.78),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_muzzle", 0.30, 0.20, 0.18),
            fur_light,
            pos=(1.42, 0.00, 0.74),
            scale=(1.08, 0.92, 0.92),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_l", 0.06, 0.18, 10),
            fur_dark,
            pos=(1.16, 0.12, 1.01),
            hpr=(0.0, 20.0, 7.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_r", 0.06, 0.18, 10),
            fur_dark,
            pos=(1.16, -0.12, 1.01),
            hpr=(0.0, 20.0, -7.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_tail", 0.08, 0.76, 12),
            fur_dark,
            pos=(-1.02, 0.00, 0.58),
            hpr=(0.0, -58.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_mane_ridge", 0.72, 0.10, 0.28),
            fur_dark,
            pos=(0.28, 0.0, 0.88),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle", 0.58, 0.48, 0.11),
            leather,
            pos=(0.08, 0.00, 0.84),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle_pad", 0.70, 0.60, 0.06),
            cloth,
            pos=(0.08, 0.00, 0.76),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_harness_chest", 0.12, 0.70, 0.05),
            leather,
            pos=(0.70, 0.0, 0.68),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_pack", 0.20, 0.40, 0.18),
            accent,
            pos=(-0.22, 0.0, 0.94),
        )
        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_eye_{'l' if side < 0 else 'r'}", 0.03, 8, 10),
                metal,
                pos=(1.34, 0.10 * side, 0.86),
                scale=(1.0, 1.0, 0.8),
            )

        legs = [(-0.58, -0.20), (-0.58, 0.20), (0.56, -0.20), (0.56, 0.20)]
        for idx, (lx, ly) in enumerate(legs):
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_leg_{idx}", 0.07, 0.72, 12),
                fur_dark,
                pos=(lx, ly, -0.16),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_paw_{idx}", 0.09, 8, 10),
                LColor(0.08, 0.08, 0.09, 1.0),
                pos=(lx, ly, -0.52),
                scale=(1.08, 1.08, 0.50),
            )

        return {
            "id": vehicle_id,
            "kind": "wolf",
            "node": root,
            "speed": 9.5,
            "run_speed": 15.2,
            "ground_offset": 0.56,
            "mount_offset": Vec3(0.0, 0.0, 0.92),
            "dismount_offset": Vec3(1.2, -0.7, 0.0),
        }

    def _spawn_stag(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.64
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        palette = self._vehicle_visual_palette("stag")
        coat = self._palette_lcolor(palette, "body")
        coat_dark = self._palette_lcolor(palette, "body_dark")
        coat_light = self._palette_lcolor(palette, "body_light")
        tack = self._palette_lcolor(palette, "leather")
        cloth = self._palette_lcolor(palette, "cloth")
        horn = self._palette_lcolor(palette, "metal")
        accent = self._palette_lcolor(palette, "accent")

        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_body", 0.54, 12, 16),
            coat,
            pos=(0.00, 0.00, 0.38),
            scale=(1.86, 0.72, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_chest", 0.30, 10, 14),
            coat_light,
            pos=(0.82, 0.00, 0.44),
            scale=(1.04, 0.82, 1.06),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_neck", 0.20, 10, 14),
            coat,
            pos=(1.08, 0.00, 0.78),
            hpr=(0.0, -20.0, 0.0),
            scale=(0.84, 0.56, 1.46),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_head", 0.24, 10, 14),
            coat_dark,
            pos=(1.42, 0.00, 1.05),
            scale=(1.18, 0.62, 0.80),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_muzzle", 0.26, 0.16, 0.14),
            coat_light,
            pos=(1.62, 0.00, 0.95),
            scale=(1.02, 0.84, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_l", 0.05, 0.16, 9),
            coat_dark,
            pos=(1.34, 0.11, 1.23),
            hpr=(0.0, 18.0, 6.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_ear_r", 0.05, 0.16, 9),
            coat_dark,
            pos=(1.34, -0.11, 1.23),
            hpr=(0.0, 18.0, -6.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_antler_l", 0.03, 0.46, 9),
            horn,
            pos=(1.26, 0.14, 1.36),
            hpr=(0.0, 8.0, 14.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_antler_r", 0.03, 0.46, 9),
            horn,
            pos=(1.26, -0.14, 1.36),
            hpr=(0.0, 8.0, -14.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_tail", 0.07, 0.48, 10),
            coat_dark,
            pos=(-1.04, 0.00, 0.70),
            hpr=(0.0, -60.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle", 0.56, 0.44, 0.10),
            tack,
            pos=(0.12, 0.00, 0.95),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_saddle_pad", 0.70, 0.56, 0.06),
            cloth,
            pos=(0.12, 0.00, 0.86),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_capelet", 0.46, 0.52, 0.10),
            accent,
            pos=(0.02, 0.0, 1.04),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_charm", 0.05, 8, 10),
            accent,
            pos=(0.92, 0.0, 0.62),
        )
        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_cone(f"{vehicle_id}_antler_tine_{'l' if side < 0 else 'r'}", 0.02, 0.22, 7),
                horn,
                pos=(1.18, 0.18 * side, 1.52),
                hpr=(0.0, 20.0, 18.0 * side),
            )

        legs = [(-0.60, -0.18), (-0.60, 0.18), (0.64, -0.18), (0.64, 0.18)]
        for idx, (lx, ly) in enumerate(legs):
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_leg_{idx}", 0.060, 0.94, 10),
                coat_dark,
                pos=(lx, ly, -0.20),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_hoof_{idx}", 0.08, 8, 10),
                LColor(0.11, 0.09, 0.08, 1.0),
                pos=(lx, ly, -0.67),
                scale=(1.02, 1.02, 0.48),
            )

        return {
            "id": vehicle_id,
            "kind": "stag",
            "node": root,
            "speed": 9.0,
            "run_speed": 14.4,
            "ground_offset": 0.64,
            "mount_offset": Vec3(0.0, 0.0, 0.98),
            "dismount_offset": Vec3(1.3, -0.65, 0.0),
        }

    def _spawn_carriage(self, vehicle_id, x, y):
        z = self._ground_height(x, y) + 0.74
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, z)

        palette = self._vehicle_visual_palette("carriage")
        wood = self._palette_lcolor(palette, "body")
        wood_dark = self._palette_lcolor(palette, "body_dark")
        wood_light = self._palette_lcolor(palette, "body_light")
        leather = self._palette_lcolor(palette, "leather")
        canopy = self._palette_lcolor(palette, "cloth")
        metal = self._palette_lcolor(palette, "metal")
        accent = self._palette_lcolor(palette, "accent")

        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_frame", 0.62, 10, 14),
            wood,
            pos=(0.0, 0.0, 0.32),
            scale=(2.48, 1.14, 0.46),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_floor", 2.28, 1.08, 0.12),
            wood_dark,
            pos=(0.0, 0.0, 0.67),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_cabin", 0.55, 10, 14),
            wood,
            pos=(0.0, 0.0, 1.16),
            scale=(1.58, 1.06, 0.96),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_cabin_trim", 1.82, 1.22, 0.08),
            accent,
            pos=(0.0, 0.0, 1.22),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_roof", 0.52, 10, 14),
            canopy,
            pos=(0.0, 0.0, 1.62),
            scale=(1.72, 1.20, 0.54),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_driver_bench", 0.54, 0.72, 0.12),
            leather,
            pos=(0.92, 0.0, 1.06),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_driver_back", 0.14, 0.72, 0.42),
            wood_dark,
            pos=(0.72, 0.0, 1.24),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_rear_trunk", 0.42, 0.78, 0.34),
            wood_light,
            pos=(-0.96, 0.0, 0.98),
        )
        self._attach_colored_geom(
            root,
            mk_cyl(f"{vehicle_id}_pole", 0.05, 1.66, 12),
            wood_dark,
            pos=(1.88, 0.0, 0.56),
            hpr=(0.0, 90.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_pole_wrap", 0.28, 0.10, 0.10),
            accent,
            pos=(1.38, 0.0, 0.56),
        )

        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_window_{'l' if side < 0 else 'r'}", 0.08, 0.42, 0.44),
                LColor(0.12, 0.10, 0.08, 0.74),
                pos=(-0.08, 0.56 * side, 1.20),
            )
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_door_panel_{'l' if side < 0 else 'r'}", 0.10, 0.54, 0.62),
                wood_dark,
                pos=(0.00, 0.58 * side, 1.00),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_lantern_{'l' if side < 0 else 'r'}", 0.08, 8, 10),
                metal,
                pos=(1.34, 0.62 * side, 1.08),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_lantern_glow_{'l' if side < 0 else 'r'}", 0.05, 8, 10),
                self._palette_lcolor(palette, "glow"),
                pos=(1.38, 0.62 * side, 1.04),
            )

        wheels = [(-1.0, -0.72), (-1.0, 0.72), (1.0, -0.72), (1.0, 0.72)]
        for idx, (wx, wy) in enumerate(wheels):
            wheel = self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_wheel_{idx}", 0.42, 0.14, 20),
                wood_dark,
                pos=(wx, wy, -0.22),
                hpr=(0.0, 0.0, 90.0),
            )
            self._attach_colored_geom(
                root,
                mk_cyl(f"{vehicle_id}_rim_{idx}", 0.45, 0.05, 20),
                metal,
                pos=(wx, wy, -0.22),
                hpr=(0.0, 0.0, 90.0),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_hub_{idx}", 0.09, 8, 10),
                accent,
                pos=(wx, wy, -0.22),
                scale=(1.0, 1.0, 0.54),
            )
            for spoke_idx in range(6):
                angle = (math.tau * float(spoke_idx)) / 6.0
                sx = wx
                sy = wy + (math.cos(angle) * 0.22)
                sz = -0.22 + (math.sin(angle) * 0.22)
                spoke = self._attach_colored_geom(
                    root,
                    mk_cyl(f"{vehicle_id}_spoke_{idx}_{spoke_idx}", 0.015, 0.24, 8),
                    wood,
                    pos=(sx, sy, sz),
                    hpr=(0.0, 90.0, math.degrees(angle)),
                )
                spoke.setScale(1.0, 1.0, 1.0)

        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_curtain_{'l' if side < 0 else 'r'}", 0.06, 0.30, 0.58),
                canopy,
                pos=(-0.26, 0.50 * side, 1.10),
            )

        return {
            "id": vehicle_id,
            "kind": "carriage",
            "node": root,
            "speed": 6.0,
            "run_speed": 9.5,
            "ground_offset": 0.74,
            "mount_offset": Vec3(0.0, 0.0, 1.08),
            "dismount_offset": Vec3(1.8, -0.8, 0.0),
        }

    def _spawn_ship(self, vehicle_id, x, y):
        water_level = -1.25
        root = self.app.render.attachNewNode(f"vehicle_{vehicle_id}")
        root.setPos(x, y, water_level)

        palette = self._vehicle_visual_palette("ship")
        wood = self._palette_lcolor(palette, "body")
        wood_dark = self._palette_lcolor(palette, "body_dark")
        wood_light = self._palette_lcolor(palette, "body_light")
        cloth = self._palette_lcolor(palette, "cloth")
        metal = self._palette_lcolor(palette, "metal")
        accent = self._palette_lcolor(palette, "accent")
        glow = self._palette_lcolor(palette, "glow")

        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_hull_mid", 0.68, 12, 16),
            wood,
            pos=(0.0, 0.0, 0.06),
            scale=(2.92, 1.18, 0.74),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_hull_bow", 0.44, 1.08, 16),
            wood,
            pos=(2.02, 0.0, 0.10),
            hpr=(0.0, 90.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_cone(f"{vehicle_id}_hull_stern", 0.52, 0.94, 16),
            wood_dark,
            pos=(-2.02, 0.0, 0.16),
            hpr=(180.0, 90.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_keel", 3.40, 0.16, 0.24),
            wood_dark,
            pos=(-0.02, 0.0, -0.34),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_deck", 3.22, 0.96, 0.11),
            wood_light,
            pos=(0.0, 0.0, 0.58),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_deck_hatch", 0.58, 0.48, 0.12),
            wood_dark,
            pos=(-0.42, 0.0, 0.70),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_stern_cabin", 0.64, 0.82, 0.46),
            accent,
            pos=(-1.20, 0.0, 0.96),
        )
        self._attach_colored_geom(
            root,
            mk_cyl(f"{vehicle_id}_mast", 0.09, 3.05, 14),
            wood_light,
            pos=(0.20, 0.0, 1.60),
        )
        self._attach_colored_geom(
            root,
            mk_cyl(f"{vehicle_id}_yard", 0.04, 1.44, 10),
            wood,
            pos=(0.24, 0.0, 2.16),
            hpr=(90.0, 0.0, 0.0),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_sail", 0.05, 1.12, 1.62),
            cloth,
            pos=(0.38, 0.0, 1.74),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_sail_stripe", 0.06, 0.94, 0.22),
            accent,
            pos=(0.42, 0.0, 1.92),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_rudder", 0.05, 0.34, 0.52),
            wood_dark,
            pos=(-1.92, 0.0, -0.04),
        )
        self._attach_colored_geom(
            root,
            mk_box(f"{vehicle_id}_bow_trim", 0.26, 0.18, 0.46),
            accent,
            pos=(2.10, 0.0, 0.56),
        )
        self._attach_colored_geom(
            root,
            mk_sphere(f"{vehicle_id}_figurehead", 0.10, 8, 10),
            glow,
            pos=(2.24, 0.0, 0.72),
            scale=(0.9, 0.7, 1.4),
        )

        for side in (-1.0, 1.0):
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_rail_{'l' if side < 0 else 'r'}", 3.00, 0.08, 0.22),
                wood_dark,
                pos=(-0.06, 0.56 * side, 0.86),
            )
            self._attach_colored_geom(
                root,
                mk_box(f"{vehicle_id}_rope_{'l' if side < 0 else 'r'}", 1.38, 0.03, 0.03),
                metal,
                pos=(0.82, 0.30 * side, 1.84),
                hpr=(0.0, -38.0, 0.0),
            )
            self._attach_colored_geom(
                root,
                mk_sphere(f"{vehicle_id}_lamp_{'l' if side < 0 else 'r'}", 0.07, 8, 10),
                glow,
                pos=(-1.44, 0.28 * side, 1.24),
            )

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
