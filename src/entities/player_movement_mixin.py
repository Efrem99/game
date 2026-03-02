"""Movement and locomotion helpers for Player."""

import math

from direct.showbase.ShowBaseGlobal import globalClock

try:
    import game_core as gc

    HAS_CORE = True
except ImportError:
    gc = None
    HAS_CORE = False


class PlayerMovementMixin:
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
            self._set_anim("mounted_move" if moved else "mounted_idle", loop=True)
        self._tick_anim_blend(dt)
        return True

    def _update_ground(self, dt, move):
        self._set_flight_fx(False)
        running = self._get_action("run")
        moving = move.len() > 0.01
        if moving:
            speed = self.run_speed if running else self.walk_speed
            move_normalized = move.normalized()
            self.cs.velocity.x = move_normalized.x * speed
            self.cs.velocity.y = move_normalized.y * speed
            angle = math.degrees(math.atan2(move_normalized.x, move_normalized.y))
            self.cs.facingDir = move_normalized
            self.actor.setH(180 - angle)
        else:
            self.cs.velocity.x *= 0.3
            self.cs.velocity.y *= 0.3

        if self._once_action("jump"):
            if self.cs.grounded:
                self.phys.applyJump(self.cs, self.data_mgr.get_move_param("jump_force"))
                self._queue_state_trigger("jump")
                self._play_sfx("jump", volume=0.68)
            else:
                self.parkour.tryLedgeGrab(self.cs, self.ps, self.phys)
                self._queue_state_trigger("ledge_grab")

        if self._once_action("roll") and move.len() > 0.01:
            self.parkour.tryVault(self.cs, self.ps, self.phys)
            self._queue_state_trigger("vault")
        if self._once_action("dash") and move.len() > 0.01:
            self.parkour.tryAirDash(self.cs, self.ps, move)
            self._queue_state_trigger("dash")
            self._queue_state_trigger("dodge")

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
            running=running,
            in_water=bool(getattr(self.cs, "inWater", False)),
        )

    def _update_flight(self, move):
        move_speed = self.flight_speed * (2.0 if self._get_action("run") else 1.0)
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
            self.cs.velocity.z *= 0.9
        self._update_flight_pose_and_fx(move)
        self._footstep_timer = 0.0

    def _final_step(self, dt):
        prev_grounded = bool(getattr(self.cs, "grounded", False))
        prev_vz = float(getattr(self.cs.velocity, "z", 0.0) or 0.0)
        self.phys.step(self.cs, dt)
        grounded = bool(getattr(self.cs, "grounded", False))
        if grounded and not prev_grounded:
            impact = abs(prev_vz)
            self._last_landing_impact_speed = impact
            if impact >= 10.0:
                self._queue_state_trigger("hard_landing")
            elif impact >= 3.0:
                self._queue_state_trigger("soft_landing")
            self._play_sfx("land", volume=0.72)
        elif grounded:
            self._last_landing_impact_speed = 0.0
        self._was_grounded = grounded
        pos = self.cs.position
        self.actor.setPos(pos.x, pos.y, pos.z)
        self._update_sword_trail()
        self._update_weapon_sheath(dt)
        self._drive_animations(dt)
        self._tick_anim_blend(dt)

    def _update_weapon_sheath(self, dt):
        if self._drawn_hold_timer > 0:
            self._drawn_hold_timer -= dt
            return
        if self._weapon_drawn:
            self._set_weapon_drawn(False)

    def _drive_animations(self, dt=0.0):
        if not hasattr(self.actor, "loop"):
            self._proc_animate()
            return

        self._run_animation_state_machine()

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
                    if current_z >= c["max_z"] - 0.5:
                        h = max(h, c["max_z"])
        return h

    def _update_python_movement(self, dt, cam_yaw, mx=None, my=None):
        self._set_flight_fx(False)
        if mx is None or my is None:
            mx, my = self._get_move_axes()

        if not hasattr(self, "_py_velocity_z"):
            self._py_velocity_z = 0.0
        if not hasattr(self, "_py_grounded"):
            self._py_grounded = True

        current_pos = self.actor.getPos()
        _ = self._get_terrain_height(current_pos.x, current_pos.y)

        if abs(mx) > 0.1 or abs(my) > 0.1:
            speed = self.run_speed if self._get_action("run") else self.walk_speed
            dx, dy = self._camera_move_vector(mx, my, cam_yaw)

            new_x = current_pos.x + dx * speed * dt
            new_y = current_pos.y + dy * speed * dt

            if self._check_collision(new_x, new_y, current_pos.z + 0.5):
                if not self._check_collision(new_x, current_pos.y, current_pos.z + 0.5):
                    new_y = current_pos.y
                elif not self._check_collision(current_pos.x, new_y, current_pos.z + 0.5):
                    new_x = current_pos.x
                else:
                    new_x = current_pos.x
                    new_y = current_pos.y

            angle = math.degrees(math.atan2(dx, dy))
            self.actor.setH(180 - angle)
            self._set_weapon_drawn(False)
            moving = True
        else:
            new_x = current_pos.x
            new_y = current_pos.y
            moving = False

        if self._once_action("jump") and self._py_grounded:
            self._py_velocity_z = 6.5
            self._py_grounded = False
            self._queue_state_trigger("jump")
            self._play_sfx("jump", volume=0.68)

        gravity = 9.8
        self._py_velocity_z -= gravity * dt
        new_z = current_pos.z + self._py_velocity_z * dt

        new_terrain_z = self._get_ground_height(new_x, new_y, current_pos.z)
        if new_z <= new_terrain_z:
            new_z = new_terrain_z
            if not self._py_grounded:
                self._queue_state_trigger("animation_finished")
                self._play_sfx("land", volume=0.72)
            self._py_velocity_z = 0.0
            self._py_grounded = True

        self.actor.setPos(new_x, new_y, new_z)

        if not self._py_grounded:
            if self._py_velocity_z > 0:
                self._set_anim("jumping", loop=True)
            else:
                self._set_anim("falling", loop=True)
        elif moving:
            state = "running" if self._get_action("run") else "walking"
            self._set_anim(state, loop=True)
        else:
            self._set_anim("idle", loop=True)
        self._update_footsteps(
            dt,
            moving=bool(moving and self._py_grounded),
            running=bool(self._get_action("run")),
            in_water=False,
        )
        self._tick_anim_blend(dt)

    def _get_terrain_height(self, x, y):
        """Query terrain height at (x,y) using world's height function if available."""
        if hasattr(self.app, "world") and self.app.world and hasattr(self.app.world, "_th"):
            try:
                return self.app.world._th(x, y)
            except Exception:
                return 0.0
        return 0.0
