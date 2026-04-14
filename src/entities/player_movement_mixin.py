"""Movement and locomotion helpers for Player."""

import logging
import math

from utils.core_runtime import gc, HAS_CORE
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import Vec3


logger = logging.getLogger("XBotRPG")


class PlayerMovementMixin:
    def _coerce_finite_scalar(self, value, fallback=0.0):
        try:
            number = float(value)
        except Exception:
            number = float(fallback)
        if not math.isfinite(number):
            return float(fallback)
        return number

    def _resolve_dodge_direction_token(self):
        getter = getattr(self, "_get_move_axes", None)
        if not callable(getter):
            return "forward"
        try:
            mx, my = getter()
            mx = float(mx or 0.0)
            my = float(my or 0.0)
        except Exception:
            return "forward"

        if abs(mx) < 0.18 and abs(my) < 0.18:
            return "forward"
        if abs(mx) >= max(abs(my), 0.34):
            return "right" if mx > 0.0 else "left"
        if my < -0.32:
            return "back"
        return "forward"

    def _emit_evasion_camera_impulse(self, direction, *, intensity=0.2):
        director = getattr(getattr(self.app, "camera_director", None), "camera_director", None)
        if not director or not hasattr(director, "emit_impact"):
            return
        direction_deg = {
            "forward": 0.0,
            "right": 90.0,
            "back": 180.0,
            "left": -90.0,
        }.get(str(direction or "").strip().lower(), 0.0)
        try:
            director.emit_impact("near_miss", intensity=float(intensity or 0.0), direction_deg=direction_deg)
        except Exception:
            pass

    def _trigger_ground_dodge(self, move, *, running=False, blur_intensity=None):
        moving = False
        try:
            moving = bool(move and move.len() > 0.01)
        except Exception:
            moving = False
        if not moving:
            return False

        direction = self._resolve_dodge_direction_token()
        hint_name = {
            "forward": "dash_forward",
            "back": "dash_back",
            "left": "dash_left",
            "right": "dash_right",
        }.get(direction, "dodging")
        apply_hints = getattr(self, "_apply_state_anim_hint_tokens", None)
        if callable(apply_hints):
            try:
                apply_hints("dodging", [hint_name, "dodging"])
            except Exception:
                pass

        trigger_dash_blur = getattr(self, "_trigger_dash_blur_fx", None)
        if callable(trigger_dash_blur):
            try:
                strength = float(blur_intensity if blur_intensity is not None else (1.0 if running else 0.9))
                trigger_dash_blur(move, intensity=strength)
            except Exception:
                pass

        self._emit_evasion_camera_impulse(direction, intensity=0.24 if running else 0.18)
        self._queue_state_trigger("dodge")
        force_state = getattr(self, "_force_action_state", None)
        if callable(force_state):
            try:
                force_state("dodging")
            except Exception:
                pass
        return True

    def _trigger_ground_roll(self, move, *, running=False, blur_intensity=None):
        moving = False
        try:
            moving = bool(move and move.len() > 0.01)
        except Exception:
            moving = False
        if not moving:
            return False

        apply_hints = getattr(self, "_apply_state_anim_hint_tokens", None)
        if callable(apply_hints):
            try:
                apply_hints("dodging", ["dodge_roll", "dodging"])
            except Exception:
                pass

        trigger_dash_blur = getattr(self, "_trigger_dash_blur_fx", None)
        if callable(trigger_dash_blur):
            try:
                strength = float(blur_intensity if blur_intensity is not None else (1.02 if running else 0.88))
                trigger_dash_blur(move, intensity=strength)
            except Exception:
                pass

        self._emit_evasion_camera_impulse("forward", intensity=0.28 if running else 0.22)
        self._queue_state_trigger("dodge")
        force_state = getattr(self, "_force_action_state", None)
        if callable(force_state):
            try:
                force_state("dodging")
            except Exception:
                pass
        return True

    def _trigger_air_dash(self, move, *, blur_intensity=None):
        moving = False
        try:
            moving = bool(move and move.len() > 0.01)
        except Exception:
            moving = False
        if not moving:
            return False

        apply_hints = getattr(self, "_apply_state_anim_hint_tokens", None)
        if callable(apply_hints):
            try:
                apply_hints("jumping", ["jump_dash", "jumping", "falling"])
                apply_hints("falling", ["jump_dash", "falling", "jumping"])
            except Exception:
                pass

        trigger_dash_blur = getattr(self, "_trigger_dash_blur_fx", None)
        if callable(trigger_dash_blur):
            try:
                trigger_dash_blur(move, intensity=float(blur_intensity if blur_intensity is not None else 1.02))
            except Exception:
                pass

        self._air_dash_until = float(globalClock.getFrameTime()) + 0.24
        self._emit_evasion_camera_impulse(self._resolve_dodge_direction_token(), intensity=0.22)
        return True

    def _trigger_flight_dash(self, move, *, move_speed, blur_intensity=None):
        moving = False
        try:
            moving = bool(move and move.len() > 0.01)
        except Exception:
            moving = False
        if not moving:
            return False

        apply_hints = getattr(self, "_apply_state_anim_hint_tokens", None)
        if callable(apply_hints):
            try:
                apply_hints("flying", ["flight_airdash", "flying"])
            except Exception:
                pass

        trigger_dash_blur = getattr(self, "_trigger_dash_blur_fx", None)
        if callable(trigger_dash_blur):
            try:
                trigger_dash_blur(move, intensity=float(blur_intensity if blur_intensity is not None else 1.08))
            except Exception:
                pass

        dash_mult = max(float(getattr(self, "flight_shift_mult", 1.45) or 1.45) + 0.22, 1.7)
        try:
            move_normalized = move.normalized()
            self.cs.velocity.x = float(move_normalized.x) * float(move_speed) * dash_mult
            self.cs.velocity.y = float(move_normalized.y) * float(move_speed) * dash_mult
        except Exception:
            pass

        self._flight_airdash_until = float(globalClock.getFrameTime()) + 0.28
        self._emit_evasion_camera_impulse(self._resolve_dodge_direction_token(), intensity=0.24)
        return True

    def _update_vehicle_control(self, dt, cam_yaw, mx, my):
        vehicle_mgr = getattr(self.app, "vehicle_mgr", None)
        if not vehicle_mgr:
            return False
        if not vehicle_mgr.is_mounted:
            return False

        self._is_flying = False
        self._set_flight_fx(False)
        self._set_weapon_drawn(False, reset_timer=True)

        running = self._get_action("run")
        moved = vehicle_mgr.update_mounted(self, dt, mx, my, running, cam_yaw)
        self._run_animation_state_machine()

        now = globalClock.getFrameTime()
        locked_mount_anim = (
            self._anim_state in {"mounting", "dismounting"}
            and self._state_lock_until > now
        )
        if not locked_mount_anim:
            mounted_vehicle = vehicle_mgr.mounted_vehicle() if hasattr(vehicle_mgr, "mounted_vehicle") else None
            mounted_kind = ""
            if isinstance(mounted_vehicle, dict):
                mounted_kind = str(mounted_vehicle.get("kind", "") or "").strip().lower()
            if not mounted_kind:
                mounted_kind = str(getattr(self, "_mount_anim_kind", "") or "").strip().lower()

            if mounted_kind in {"ship", "boat"}:
                target_state = "mounted_ship_move" if moved else "mounted_ship_idle"
            else:
                target_state = "mounted_move" if moved else "mounted_idle"
            self._set_anim(target_state, loop=True)
        self._tick_anim_blend(dt)
        return True

    def _update_ground(self, dt, move):
        self._set_flight_fx(False)
        running = self._get_action("run")
        crouched = bool(getattr(self, "_stealth_crouch", False) and not bool(getattr(self, "_is_flying", False)))
        if crouched and running:
            running = False
        water_cfg = getattr(getattr(self.app, "data_mgr", None), "water_config", {}) or {}
        water_level = float(water_cfg.get("water_level", -0.4) if isinstance(water_cfg, dict) else -0.4)
        pos = getattr(self.actor, "getPos", lambda render: None)(self.app.render)
        if pos is not None:
            in_water = bool(getattr(self.cs, "inWater", False) or getattr(self, "_py_in_water", False))
            terrain_z = None
            water_surface = None
            world = getattr(self.app, "world", None)
            if world and hasattr(world, "sample_water_height"):
                try:
                    sampled = float(world.sample_water_height(float(pos.x), float(pos.y)))
                    if math.isfinite(sampled):
                        water_surface = sampled
                    else:
                        water_surface = None
                except Exception:
                    water_surface = None
            try:
                terrain_z = self._coerce_finite_scalar(
                    self._get_ground_height(float(pos.x), float(pos.y), float(pos.z)),
                    float(pos.z),
                )
            except Exception:
                terrain_z = self._coerce_finite_scalar(float(pos.z), 0.0)
            if water_surface is not None:
                # Only trust sampled water when it is actually above the local
                # terrain. This prevents a global sea fallback level from
                # turning arbitrary underground positions into fake swim states.
                if float(water_surface) > (float(terrain_z) + 0.05) and float(pos.z) < (float(water_surface) - 0.02):
                    in_water = True
            elif float(pos.z) < water_level and float(water_level) > (float(terrain_z) + 0.05):
                in_water = True
            self.cs.inWater = in_water
            if in_water:
                surface = float(water_surface) if water_surface is not None else float(water_level)
                depth = surface - float(pos.z)
                buoyancy = max(0.0, min(30.0, depth * 20.0))
                dt = min(0.05, globalClock.getDt())
                self.cs.velocity.z += (buoyancy - 9.0) * dt
                crouched = False
                running = False
        moving = move.len() > 0.01
        motion_plan = getattr(self, "_motion_plan", {}) if isinstance(getattr(self, "_motion_plan", {}), dict) else {}
        motion = motion_plan.get("motion_plan", {}) if isinstance(motion_plan, dict) else {}
        gait_mult = 1.0
        try:
            gait_mult = max(0.45, min(1.15, float(motion.get("gait_speed_mult", 1.0) or 1.0)))
        except Exception:
            gait_mult = 1.0
        if moving:
            stealth_mult = 0.56 if crouched else 1.0
            speed = (self.run_speed if running else self.walk_speed) * gait_mult * stealth_mult
            move_normalized = move.normalized()
            self.cs.velocity.x = move_normalized.x * speed
            self.cs.velocity.y = move_normalized.y * speed
            angle = math.degrees(math.atan2(move_normalized.x, move_normalized.y))
            self.cs.facingDir = move_normalized
            self.actor.setH(180 - angle)
            turn_type = str(motion.get("turn_type", "") or "").strip().lower()
            now = globalClock.getFrameTime()
            if turn_type and (now - float(getattr(self, "_last_turn_trigger_time", 0.0))) >= 0.22:
                self._queue_state_trigger(turn_type)
                self._last_turn_trigger_time = now
        else:
            self.cs.velocity.x = 0.0
            self.cs.velocity.y = 0.0

        if self._once_action("jump") and not getattr(self.cs, "inWater", False):
            if self.cs.grounded:
                if crouched:
                    self._set_stealth_crouch(False)
                jump_force = float(self.data_mgr.get_move_param("jump_force") or 9.5)
                try:
                    jump_force *= max(0.35, min(1.25, float(motion.get("jump_modifier", 1.0) or 1.0)))
                except Exception:
                    pass
                self.phys.applyJump(self.cs, jump_force)
                self._queue_state_trigger("jump")
                self._play_sfx("jump", volume=0.68)
            else:
                self.parkour.tryLedgeGrab(self.cs, self.ps, self.phys)
                self._queue_state_trigger("ledge_grab")

        if self._once_action("roll"):
            self._trigger_ground_roll(move, running=running, blur_intensity=1.0 if running else 0.86)
        if self._once_action("dash") and move.len() > 0.01:
            if bool(getattr(self.cs, "grounded", False)):
                self._trigger_ground_dodge(move, running=running, blur_intensity=1.08 if running else 0.94)
                self._queue_state_trigger("dash")
            else:
                try:
                    self.parkour.tryAirDash(self.cs, self.ps, move)
                except Exception:
                    pass
                self._trigger_air_dash(move, blur_intensity=1.02 if running else 0.96)

        if move.len() > 0.01 and not self.cs.grounded:
            try:
                if self.parkour.tryWallRun(self.cs, self.ps, self.phys):
                    self._queue_state_trigger("wall_contact")
            except Exception:
                pass

        self.parkour.update(
            self.cs,
            self.ps,
            self.phys,
            dt,
            self._get_action("jump"),
            moving,
            move,
        )
        self._sync_wall_contact_state()
        self._update_footsteps(
            dt,
            moving=moving and bool(self.cs.grounded),
            running=running and (not crouched),
            in_water=bool(getattr(self.cs, "inWater", False)),
        )

    def _update_flight(self, move):
        if bool(getattr(self, "_stealth_crouch", False)):
            self._set_stealth_crouch(False)
        move_speed = self.flight_speed * (float(getattr(self, "flight_shift_mult", 1.45) or 1.45) if self._get_action("run") else 1.0)
        if move.len() > 0.01:
            move_normalized = move.normalized()
            self.cs.velocity.x = move_normalized.x * move_speed
            self.cs.velocity.y = move_normalized.y * move_speed
            self.actor.setH(180 - math.degrees(math.atan2(move_normalized.x, move_normalized.y)))
        else:
            self.cs.velocity.x *= 0.9
            self.cs.velocity.y *= 0.9

        if self._get_action("flight_up"):
            self.cs.velocity.z = move_speed
        elif self._get_action("flight_down"):
            self.cs.velocity.z = -move_speed
        else:
            dt = min(0.05, max(0.001, globalClock.getDt()))
            self.cs.velocity.z -= 4.0 * dt
            self.cs.velocity.z *= 0.94
        if self._once_action("dash"):
            self._trigger_flight_dash(move, move_speed=move_speed, blur_intensity=1.08 if self._get_action("run") else 1.0)
        self._update_flight_pose_and_fx(move)
        self._footstep_timer = 0.0

    def _final_step(self, dt):
        prev_grounded = bool(getattr(self.cs, "grounded", False))
        prev_vz = float(getattr(self.cs.velocity, "z", 0.0) or 0.0)
        self.phys.step(self.cs, dt)
        if not bool(getattr(self.cs, "inWater", False)):
            try:
                pos = self.cs.position
                terrain_z = self._coerce_finite_scalar(
                    self._get_ground_height(float(pos.x), float(pos.y), float(pos.z)),
                    float(pos.z),
                )
                # Flying should not allow the actor to disappear below the terrain.
                # Clamp invalid under-ground positions back to the sampled surface
                # instead of letting the runtime drift under the floor.
                if float(pos.z) < (terrain_z - 0.02):
                    pos.z = terrain_z
                    if float(getattr(self.cs.velocity, "z", 0.0) or 0.0) < 0.0:
                        self.cs.velocity.z = 0.0
                    self.cs.grounded = True
            except Exception:
                pass
        grounded = bool(getattr(self.cs, "grounded", False))
        motion_plan = getattr(self, "_motion_plan", {}) if isinstance(getattr(self, "_motion_plan", {}), dict) else {}
        motion = motion_plan.get("motion_plan", {}) if isinstance(motion_plan, dict) else {}
        if grounded and not prev_grounded:
            impact = abs(prev_vz)
            self._last_landing_impact_speed = impact
            self._landing_anim_hold = 0.16 if impact < 6.0 else 0.26
            if impact >= 10.0:
                self._queue_state_trigger("hard_landing")
            elif impact >= 3.0:
                self._queue_state_trigger("soft_landing")
            landing = str(motion.get("landing_prep", "") or "").strip().lower()
            if landing == "roll_land":
                self._queue_state_trigger("roll_land")
            elif landing == "stumble_land":
                self._queue_state_trigger("stumble_land")
            elif landing == "collapse":
                self._queue_state_trigger("collapse")
            self._play_sfx("land", volume=0.72)
            director = getattr(getattr(self.app, "camera_director", None), "camera_director", None)
            if director and hasattr(director, "emit_impact"):
                try:
                    if impact >= 10.0:
                        director.emit_impact("hard_fall", intensity=min(1.6, impact / 10.0))
                    elif impact >= 4.5:
                        director.emit_impact("hit", intensity=min(1.0, impact / 12.0))
                except Exception:
                    pass
            time_fx = getattr(getattr(self.app, "time_fx", None), "time_fx", None)
            if time_fx and hasattr(time_fx, "trigger"):
                try:
                    if impact >= 10.0:
                        time_fx.trigger("hard_fall", duration=0.20)
                    elif impact >= 4.5:
                        time_fx.trigger("micro_hit", duration=0.10)
                except Exception:
                    pass
        elif grounded:
            self._last_landing_impact_speed = 0.0
            self._landing_anim_hold = max(
                0.0,
                float(getattr(self, "_landing_anim_hold", 0.0) or 0.0) - max(0.0, float(dt or 0.0)),
            )
            balance = str(motion.get("balance_correction", "") or "").strip().lower()
            if balance in {"stumble", "near_fall", "fall"}:
                self._queue_state_trigger(balance)
                director = getattr(getattr(self.app, "camera_director", None), "camera_director", None)
                if director and hasattr(director, "emit_impact"):
                    try:
                        if balance == "fall":
                            director.emit_impact("heavy", intensity=0.85)
                        elif balance == "near_fall":
                            director.emit_miss("near_miss", intensity=0.55)
                        else:
                            director.emit_impact("hit", intensity=0.35)
                    except Exception:
                        pass
        self._was_grounded = grounded
        pos = self.cs.position
        offset = getattr(self, "_visual_height_offset", 0.0)
        self.actor.setPos(pos.x, pos.y, pos.z + offset)
        update_dash_blur = getattr(self, "_update_dash_blur_fx", None)
        if callable(update_dash_blur):
            try:
                update_dash_blur(dt)
            except Exception:
                pass
        self._update_sword_trail()
        self._update_weapon_sheath(dt)
        self._drive_animations(dt)
        self._tick_anim_blend(dt)

    def _update_weapon_sheath(self, dt):
        if bool(getattr(self, "_is_flying", False)):
            if bool(getattr(self, "_weapon_drawn", False)):
                self._drawn_hold_timer = max(float(getattr(self, "_drawn_hold_timer", 0.0) or 0.0), 0.12)
            return
        if float(getattr(self, "_drawn_hold_timer", 0.0)) > 0:
            self._drawn_hold_timer -= dt
            return
        if bool(getattr(self, "_weapon_drawn", False)):
            self._set_weapon_drawn(False)

    def _drive_animations(self, dt=0.0):
        if not hasattr(self.actor, "loop"):
            self._proc_animate()
            return

        sync_parkour_hints = getattr(self, "_sync_parkour_runtime_hints", None)
        if callable(sync_parkour_hints):
            try:
                sync_parkour_hints()
            except Exception:
                pass

        self._run_animation_state_machine()
        update_contextual_sfx = getattr(self, "_update_contextual_state_sfx", None)
        if callable(update_contextual_sfx):
            try:
                update_contextual_sfx()
            except Exception:
                pass

        # Runtime guard against silent animation dropouts (visual T-pose symptom).
        current_anim = ""
        try:
            current_anim = str(self.actor.getCurrentAnim() or "").strip()
        except Exception:
            current_anim = ""
        if current_anim:
            self._anim_no_clip_time = 0.0
            update_ik = getattr(self, "_update_parkour_ik", None)
            if callable(update_ik):
                try:
                    update_ik(dt)
                except Exception:
                    pass
            return
        self._anim_no_clip_time = float(getattr(self, "_anim_no_clip_time", 0.0) or 0.0) + max(0.0, float(dt or 0.0))
        no_clip_threshold = 0.35
        if bool(getattr(self.cs, "grounded", False)) and not bool(getattr(self, "_is_flying", False)):
            no_clip_threshold = 0.10
        if self._anim_no_clip_time >= no_clip_threshold:
            dropout_marker = (
                str(getattr(self, "_anim_state", "") or "").strip().lower(),
                str(getattr(self, "_anim_clip", "") or "").strip(),
                bool(getattr(self, "_anim_blend_transition", None)),
            )
            if dropout_marker != getattr(self, "_anim_dropout_logged", None):
                self._anim_dropout_logged = dropout_marker
                logger.warning(
                    "[Anim][DROPOUT] No current animation is active for %.2fs while state='%s' clip='%s' blend_active=%s. "
                    "Triggering safe clip recovery to prevent bind pose.",
                    self._anim_no_clip_time,
                    dropout_marker[0] or "-",
                    dropout_marker[1] or "-",
                    dropout_marker[2],
                )
            try:
                self._force_safe_idle_anim()
            except Exception:
                pass
            self._anim_no_clip_time = 0.0
        update_ik = getattr(self, "_update_parkour_ik", None)
        if callable(update_ik):
            try:
                update_ik(dt)
            except Exception:
                pass

    def _proc_animate(self, dt=0.0):
        if not hasattr(self, "_proc_root"):
            return
        frame_time = globalClock.getFrameTime()
        speed = math.sqrt(self.cs.velocity.x**2 + self.cs.velocity.y**2) if self.cs else 0
        cycle = math.sin(frame_time * max(5, speed * 2))
        if hasattr(self, "_r_leg"):
            self._r_leg.setP(cycle * 35)
            self._l_leg.setP(-cycle * 35)
            self._r_arm.setP(-cycle * 25)
            self._l_arm.setP(cycle * 25)

    @property
    def enemies(self):
        return self.app.enemy_proxies if hasattr(self.app, "enemy_proxies") else []

    def _check_collision(self, x, y, z):
        if not hasattr(self.app, "world") or not getattr(self.app.world, "colliders", None):
            return False
        pr = 0.4  # player radius
        ph = 1.8  # player height
        for c in self.app.world.colliders:
            if (
                x + pr > c["min_x"]
                and x - pr < c["max_x"]
                and y + pr > c["min_y"]
                and y - pr < c["max_y"]
                and z + ph > c["min_z"]
                and z < c["max_z"]
            ):
                return True
        return False

    def _get_ground_height(self, x, y, current_z):
        h = self._get_terrain_height(x, y)
        if hasattr(self.app, "world") and getattr(self.app.world, "colliders", None):
            pr = 0.4
            for c in self.app.world.colliders:
                if (
                    x + pr > c["min_x"]
                    and x - pr < c["max_x"]
                    and y + pr > c["min_y"]
                    and y - pr < c["max_y"]
                ):
                    top_z = float(c.get("max_z", h) or h)
                    bottom_z = float(c.get("min_z", top_z) or top_z)
                    within_platform_volume = (bottom_z - 0.25) <= float(current_z) <= (top_z + 1.25)
                    if within_platform_volume:
                        h = max(h, top_z)
        return h

    def _update_python_movement(self, dt, cam_yaw, mx=None, my=None):
        self._set_flight_fx(False)
        if mx is None or my is None:
            mx, my = self._get_move_axes()
        dt = max(0.0, self._coerce_finite_scalar(dt, 0.0))
        cam_yaw = self._coerce_finite_scalar(cam_yaw, 0.0)
        motion_plan = getattr(self, "_motion_plan", {})
        if not isinstance(motion_plan, dict):
            motion_plan = {}
        motion = motion_plan.get("motion_plan", {})
        if not isinstance(motion, dict):
            motion = {}
        try:
            gait_mult = max(0.45, min(1.15, float(motion.get("gait_speed_mult", 1.0) or 1.0)))
        except Exception:
            gait_mult = 1.0
        try:
            jump_mult = max(0.35, min(1.25, float(motion.get("jump_modifier", 1.0) or 1.0)))
        except Exception:
            jump_mult = 1.0

        if not hasattr(self, "_py_velocity_z"):
            self._py_velocity_z = 0.0
        if not hasattr(self, "_py_grounded"):
            self._py_grounded = True
        if not hasattr(self, "_py_landing_timer"):
            self._py_landing_timer = 0.0
        if not hasattr(self, "_py_in_water"):
            self._py_in_water = False

        current_pos = self.actor.getPos()
        current_x = self._coerce_finite_scalar(getattr(current_pos, "x", 0.0), 0.0)
        current_y = self._coerce_finite_scalar(getattr(current_pos, "y", 0.0), 0.0)
        current_z = self._coerce_finite_scalar(getattr(current_pos, "z", 0.0), 0.0)
        in_water = bool(getattr(self, "_py_in_water", False))
        if self.cs and hasattr(self.cs, "inWater"):
            try:
                in_water = bool(getattr(self.cs, "inWater", False))
            except Exception:
                pass

        crouched = bool(getattr(self, "_stealth_crouch", False) and not bool(getattr(self, "_is_flying", False)))
        running = bool(self._get_action("run") and (not crouched))
        if in_water:
            running = False

        dx, dy = 0.0, 0.0
        if abs(mx) > 0.1 or abs(my) > 0.1:
            stealth_mult = 0.56 if crouched else 1.0
            speed = (self.run_speed if running else self.walk_speed) * gait_mult * stealth_mult
            dx, dy = self._camera_move_vector(mx, my, cam_yaw)
            dx = self._coerce_finite_scalar(dx, 0.0)
            dy = self._coerce_finite_scalar(dy, 0.0)

            new_x = self._coerce_finite_scalar(current_x + (dx * speed * dt), current_x)
            new_y = self._coerce_finite_scalar(current_y + (dy * speed * dt), current_y)

            if self._check_collision(new_x, new_y, current_z + 0.5):
                if not self._check_collision(new_x, current_y, current_z + 0.5):
                    new_y = current_y
                elif not self._check_collision(current_x, new_y, current_z + 0.5):
                    new_x = current_x
                else:
                    new_x = current_x
                    new_y = current_y

            moving = (abs(dx) > 1e-6) or (abs(dy) > 1e-6)
            if moving:
                angle = self._coerce_finite_scalar(math.degrees(math.atan2(dx, dy)), 0.0)
                try:
                    self.actor.setH(self._coerce_finite_scalar(180.0 - angle, 0.0))
                except Exception:
                    pass
        else:
            new_x = current_x
            new_y = current_y
            moving = False

        if self._once_action("jump") and self._py_grounded and (not in_water):
            if crouched:
                self._set_stealth_crouch(False)
            self._py_velocity_z = 6.5 * jump_mult
            self._py_grounded = False
            self._queue_state_trigger("jump")
            self._play_sfx("jump", volume=0.68)

        dash_move = type("_DashMove", (), {"x": dx, "y": dy, "len": lambda self: 1.0 if moving else 0.0})()
        if self._once_action("roll") and moving and self._py_grounded and (not in_water):
            self._trigger_ground_roll(dash_move, running=running, blur_intensity=0.98 if running else 0.84)
        if self._once_action("dash") and moving and (not in_water):
            if self._py_grounded:
                self._trigger_ground_dodge(dash_move, running=running, blur_intensity=1.04 if running else 0.9)
                self._queue_state_trigger("dash")
            else:
                try:
                    self.parkour.tryAirDash(self.cs, self.ps, dash_move)
                except Exception:
                    pass
                self._trigger_air_dash(dash_move, blur_intensity=1.0 if running else 0.94)

        prev_vz = float(self._py_velocity_z)
        if in_water:
            self._py_velocity_z = 0.0
            new_z = current_z
            self._py_grounded = True
            self._last_landing_impact_speed = 0.0
        else:
            gravity = 9.8
            self._py_velocity_z -= gravity * dt
            new_z = self._coerce_finite_scalar(current_z + (self._py_velocity_z * dt), current_z)

        new_terrain_z = self._coerce_finite_scalar(
            self._get_ground_height(new_x, new_y, current_z),
            current_z,
        )
        if (not in_water) and new_z <= new_terrain_z:
            new_z = new_terrain_z
            if not self._py_grounded:
                impact = abs(prev_vz)
                self._last_landing_impact_speed = impact
                self._py_landing_timer = max(float(getattr(self, "_py_landing_timer", 0.0) or 0.0), 0.16 if impact < 6.0 else 0.24)
                if impact >= 9.5:
                    self._queue_state_trigger("hard_landing")
                elif impact >= 3.0:
                    self._queue_state_trigger("soft_landing")
                self._play_sfx("land", volume=0.72)
            else:
                self._last_landing_impact_speed = 0.0
            self._py_velocity_z = 0.0
            self._py_grounded = True

        new_x = self._coerce_finite_scalar(new_x, current_x)
        new_y = self._coerce_finite_scalar(new_y, current_y)
        new_z = self._coerce_finite_scalar(new_z, max(current_z, new_terrain_z))
        
        offset = getattr(self, "_visual_height_offset", 0.0)
        self.actor.setPos(new_x, new_y, new_z + offset)
        
        if self._py_grounded:
            self._py_landing_timer = max(0.0, float(getattr(self, "_py_landing_timer", 0.0) or 0.0) - max(0.0, float(dt)))
        self._run_animation_state_machine()
        update_contextual_sfx = getattr(self, "_update_contextual_state_sfx", None)
        if callable(update_contextual_sfx):
            try:
                update_contextual_sfx()
            except Exception:
                pass
        self._update_footsteps(
            dt,
            moving=bool(moving and self._py_grounded),
            running=bool(running),
            in_water=bool(in_water),
        )
        update_dash_blur = getattr(self, "_update_dash_blur_fx", None)
        if callable(update_dash_blur):
            try:
                update_dash_blur(dt)
            except Exception:
                pass
        # Handle Mode Toggling (e.g., flight)
        if self._once_action("flight_toggle") or self._once_action("special_extra"):
            if getattr(self, "_movement_mode", "walk") == "flight":
                self._movement_mode = "walk"
                self._py_grounded = False # Fall if currently in air
                logger.info("[Player] Flight deactivated (Landing).")
            else:
                self._movement_mode = "flight"
                self._py_grounded = False
                logger.info("[Player] Flight activated.")

        is_flying = getattr(self, "_movement_mode", "walk") == "flight"
        self._is_flying = is_flying

        if is_flying:
            self._update_flight_python(dt, dx, dy if moving else 0.0, mx, my)
            return

        self._tick_anim_blend(dt)

    def _update_flight_python(self, dt, dx, dy, mx, my):
        # Python-only flight logic
        move_speed = self.flight_speed * (float(getattr(self, "flight_shift_mult", 1.45) or 1.45) if self._get_action("run") else 1.0)

        # Horizontal
        new_x = self.actor.getX() + dx * move_speed * dt
        new_y = self.actor.getY() + dy * move_speed * dt
        
        # Vertical
        vz = 0.0
        if self._get_action("flight_up") or self._get_action("jump"):
            vz = move_speed * 0.8
        elif self._get_action("flight_down") or self._get_action("crouch"):
            vz = -move_speed * 0.8
        
        new_z = self.actor.getZ() + vz * dt
        terrain_z = self._coerce_finite_scalar(
            self._get_ground_height(new_x, new_y, new_z),
            new_z,
        )
        if new_z < terrain_z:
            new_z = terrain_z
        
        # Collision (simple)
        if self._check_collision(new_x, new_y, new_z):
            # Slide or stop
            pass
        else:
            offset = getattr(self, "_visual_height_offset", 0.0)
            self.actor.setPos(new_x, new_y, new_z + offset)
            if self.cs:
                self.cs.position = Vec3(new_x, new_y, new_z)
        
        dash_pressed = self._once_action("dash")
        if dash_pressed and (abs(mx) > 0.1 or abs(my) > 0.1):
            self._trigger_flight_dash(
                type("_Move", (), {"len": lambda _self: 1.0, "normalized": lambda _self: type("_Norm", (), {"x": dx, "y": dy, "z": 0.0})()})(),
                move_speed=move_speed,
                blur_intensity=1.08 if self._get_action("run") else 1.0,
            )
            dash_mult = max(float(getattr(self, "flight_shift_mult", 1.45) or 1.45) + 0.22, 1.7)
            new_x = self.actor.getX() + dx * move_speed * dash_mult * dt
            new_y = self.actor.getY() + dy * move_speed * dash_mult * dt

        if abs(mx) > 0.1 or abs(my) > 0.1:
            angle = math.degrees(math.atan2(dx, dy))
            self.actor.setH(180 - angle)
            
        self._update_flight_pose_and_fx(type("_Move", (), {"len": lambda: 1.0 if (abs(mx)>0.1 or abs(my)>0.1) else 0.0})())
        run_fsm = getattr(self, "_run_animation_state_machine", None)
        if callable(run_fsm):
            try:
                run_fsm()
            except Exception:
                pass
        update_contextual_sfx = getattr(self, "_update_contextual_state_sfx", None)
        if callable(update_contextual_sfx):
            try:
                update_contextual_sfx()
            except Exception:
                pass
        self._tick_anim_blend(dt)

    def _get_terrain_height(self, x, y):
        """Query terrain height at (x,y) using world's height function if available."""
        if hasattr(self.app, "world") and self.app.world and hasattr(self.app.world, "_th"):
            try:
                return self.app.world._th(x, y)
            except Exception:
                return 0.0
        return 0.0
