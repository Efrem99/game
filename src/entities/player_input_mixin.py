"""Player input helpers and key state handling."""

import math


class PlayerInputMixin:
    def _normalize_binding_token(self, token):
        value = str(token or "").strip().lower()
        if not value or value == "none":
            return ""
        return value

    def _setup_input(self):
        source_bindings = self.data_mgr.controls.get("bindings", {})
        gamepad_bindings = self.data_mgr.controls.get("gamepad_bindings", {})
        self._bindings = {}
        for action, key in source_bindings.items():
            resolved = self._normalize_binding_token(self.data_mgr.get_binding(action) or key)
            if resolved:
                self._bindings[action] = resolved
        self._gamepad_bindings = {}
        if isinstance(gamepad_bindings, dict):
            for action, key in gamepad_bindings.items():
                resolved = self._normalize_binding_token(key)
                if resolved:
                    self._gamepad_bindings[action] = resolved

        self._ru_map = {
            "w": "\u0446",
            "a": "\u0444",
            "s": "\u044b",
            "d": "\u0432",
            "q": "\u0439",
            "e": "\u0443",
            "r": "\u043a",
            "f": "\u0430",
            "z": "\u044f",
            "x": "\u0447",
            "c": "\u0441",
            "v": "\u043c",
            "i": "\u0448",
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
        }
        unique_keys = set(self._bindings.values()) | set(self._gamepad_bindings.values())
        all_listeners = set(unique_keys)
        for key in unique_keys:
            if key in self._ru_map:
                all_listeners.add(self._ru_map[key])

        for key in all_listeners:
            self._keys[key] = False
            self.app.accept(key, self._key_down, [key])
            self.app.accept(f"{key}-up", self._key_up, [key])
        self._consumed = {key: False for key in all_listeners}

    def _video_bot_input_locked(self):
        app = getattr(self, "app", None)
        if not app:
            return False
        return bool(
            getattr(app, "_video_bot_enabled", False)
            and getattr(app, "_video_bot_capture_input", False)
        )

    def _get_action(self, action):
        k1 = self._normalize_binding_token(self.data_mgr.get_binding(action) or self._bindings.get(action))
        k2 = self._ru_map.get(k1)
        k3 = self._normalize_binding_token(
            self.data_mgr.controls.get("gamepad_bindings", {}).get(action)
            if isinstance(self.data_mgr.controls.get("gamepad_bindings", {}), dict)
            else self._gamepad_bindings.get(action)
        )
        v1 = self._keys.get(k1, False) if k1 else False
        v2 = self._keys.get(k2, False) if k2 else False
        v3 = self._keys.get(k3, False) if k3 else False
        return v1 or v2 or v3

    def _once_action(self, action):
        k1 = self._normalize_binding_token(self.data_mgr.get_binding(action) or self._bindings.get(action))
        k2 = self._ru_map.get(k1)
        k3 = self._normalize_binding_token(
            self.data_mgr.controls.get("gamepad_bindings", {}).get(action)
            if isinstance(self.data_mgr.controls.get("gamepad_bindings", {}), dict)
            else self._gamepad_bindings.get(action)
        )
        for key in [k1, k2, k3]:
            if key and self._keys.get(key) and not self._consumed.get(key):
                self._consumed[key] = True
                return True
        return False

    def _key_down(self, key, synthetic=False):
        if self._video_bot_input_locked() and not bool(synthetic):
            return
        self._keys[key] = True

    def _key_up(self, key, synthetic=False):
        if self._video_bot_input_locked() and not bool(synthetic):
            return
        self._keys[key] = False
        self._consumed[key] = False

    def _get_move_axes(self):
        mx = my = 0.0
        if self._get_action("forward"):
            my += 1.0
        if self._get_action("backward"):
            my -= 1.0
        if self._get_action("left"):
            mx -= 1.0
        if self._get_action("right"):
            mx += 1.0
        gp_axes = getattr(getattr(self, "app", None), "_gp_axes", {})
        if isinstance(gp_axes, dict) and not self._video_bot_input_locked():
            DEADZONE = 0.15
            try:
                val = float(gp_axes.get("move_x", 0.0) or 0.0)
                if abs(val) > DEADZONE:
                    mx += val
            except Exception:
                pass
            try:
                val = float(gp_axes.get("move_y", 0.0) or 0.0)
                if abs(val) > DEADZONE:
                    my += val
            except Exception:
                pass
        mx = max(-1.0, min(1.0, mx))
        my = max(-1.0, min(1.0, my))
        return mx, my

    def _camera_move_vector(self, mx, my, cam_yaw):
        yaw_radians = math.radians(cam_yaw)
        return (
            (mx * math.cos(yaw_radians)) + (my * math.sin(yaw_radians)),
            (-mx * math.sin(yaw_radians)) + (my * math.cos(yaw_radians)),
        )
