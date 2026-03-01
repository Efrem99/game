"""Player input helpers and key state handling."""

import math


class PlayerInputMixin:
    def _setup_input(self):
        source_bindings = self.data_mgr.controls.get("bindings", {})
        self._bindings = {}
        for action, key in source_bindings.items():
            resolved = self.data_mgr.get_binding(action) or key
            if resolved:
                self._bindings[action] = resolved

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
        unique_keys = set(self._bindings.values())
        all_listeners = set(unique_keys)
        for key in unique_keys:
            if key in self._ru_map:
                all_listeners.add(self._ru_map[key])

        for key in all_listeners:
            self._keys[key] = False
            self.app.accept(key, self._key_down, [key])
            self.app.accept(f"{key}-up", self._key_up, [key])
        self._consumed = {key: False for key in all_listeners}

    def _get_action(self, action):
        k1 = self.data_mgr.get_binding(action) or self._bindings.get(action)
        k2 = self._ru_map.get(k1)
        v1 = self._keys.get(k1, False) if k1 else False
        v2 = self._keys.get(k2, False) if k2 else False
        return v1 or v2

    def _once_action(self, action):
        k1 = self.data_mgr.get_binding(action) or self._bindings.get(action)
        k2 = self._ru_map.get(k1)
        for key in [k1, k2]:
            if key and self._keys.get(key) and not self._consumed.get(key):
                self._consumed[key] = True
                return True
        return False

    def _key_down(self, key):
        self._keys[key] = True

    def _key_up(self, key):
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
        return mx, my

    def _camera_move_vector(self, mx, my, cam_yaw):
        yaw_radians = math.radians(cam_yaw)
        return (
            (mx * math.cos(yaw_radians)) + (my * math.sin(yaw_radians)),
            (-mx * math.sin(yaw_radians)) + (my * math.cos(yaw_radians)),
        )
