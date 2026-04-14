import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _Vec3:
    def __init__(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _CameraGuardDummy:
    _sanitize_camera_transform = XBotApp._sanitize_camera_transform

    def __init__(self):
        self._cam_dist = 22.0


class _TransformStub:
    def getMat(self):
        return "mat"


class _CameraNodeStub:
    def __init__(self, fail_probe_once=False):
        self._pos = _Vec3(0.0, 0.0, 0.0)
        self._scale = _Vec3(1.0, 1.0, 1.0)
        self._hpr = _Vec3(0.0, 0.0, 0.0)
        self._fail_probe_once = bool(fail_probe_once)
        self.look_targets = []

    def setPos(self, value):
        if hasattr(value, "x"):
            self._pos = _Vec3(value.x, value.y, value.z)
        else:
            self._pos = _Vec3(*value)

    def setHpr(self, h, p=None, r=None):
        if p is None and hasattr(h, "x"):
            self._hpr = _Vec3(h.x, h.y, h.z)
        else:
            self._hpr = _Vec3(h, p, r)

    def lookAt(self, value):
        self.look_targets.append(_Vec3(value.x, value.y, value.z))

    def getPos(self, *_):
        return _Vec3(self._pos.x, self._pos.y, self._pos.z)

    def getScale(self, *_):
        return _Vec3(self._scale.x, self._scale.y, self._scale.z)

    def getHpr(self, *_):
        return _Vec3(self._hpr.x, self._hpr.y, self._hpr.z)

    def getTransform(self, *_):
        if self._fail_probe_once:
            self._fail_probe_once = False
            raise AssertionError("has_mat()")
        return _TransformStub()

    def getNetTransform(self):
        return _TransformStub()


class _CameraCommitDummy:
    _is_finite_components = XBotApp._is_finite_components
    _probe_scene_node_matrices = XBotApp._probe_scene_node_matrices
    _probe_scene_node_transform = XBotApp._probe_scene_node_transform
    _sanitize_camera_transform = XBotApp._sanitize_camera_transform
    _commit_camera_transform = XBotApp._commit_camera_transform

    def __init__(self, fail_probe_once=False):
        self._cam_dist = 22.0
        self.camera = _CameraNodeStub(fail_probe_once=fail_probe_once)
        self.render = object()


class AppCameraTransformGuardTests(unittest.TestCase):
    def test_sanitize_camera_transform_keeps_finite_values(self):
        app = _CameraGuardDummy()
        center = _Vec3(1.0, 2.0, 3.0)
        cam_pos = _Vec3(8.0, -6.0, 9.0)
        target = _Vec3(1.0, 2.0, 4.8)

        out_pos, out_target = app._sanitize_camera_transform(cam_pos, target, center, 3.0)

        self.assertEqual((8.0, -6.0, 9.0), (out_pos.x, out_pos.y, out_pos.z))
        self.assertEqual((1.0, 2.0, 4.8), (out_target.x, out_target.y, out_target.z))

    def test_sanitize_camera_transform_replaces_nan_values_with_follow_fallback(self):
        app = _CameraGuardDummy()
        center = _Vec3(4.0, 5.0, 6.0)
        cam_pos = _Vec3(math.nan, 1.0, 2.0)
        target = _Vec3(4.0, math.inf, 7.0)

        out_pos, out_target = app._sanitize_camera_transform(cam_pos, target, center, 6.0)

        self.assertTrue(all(math.isfinite(v) for v in (out_pos.x, out_pos.y, out_pos.z)))
        self.assertTrue(all(math.isfinite(v) for v in (out_target.x, out_target.y, out_target.z)))
        self.assertAlmostEqual(4.0, out_target.x, places=4)
        self.assertAlmostEqual(5.0, out_target.y, places=4)
        self.assertAlmostEqual(7.8, out_target.z, places=4)
        self.assertAlmostEqual(4.0, out_pos.x, places=4)
        self.assertAlmostEqual(-13.0, out_pos.y, places=4)
        self.assertAlmostEqual(16.0, out_pos.z, places=4)

    def test_commit_camera_transform_falls_back_when_probe_detects_invalid_transform(self):
        app = _CameraCommitDummy(fail_probe_once=True)
        center = _Vec3(4.0, 5.0, 6.0)
        cam_pos = _Vec3(8.0, -6.0, 9.0)
        target = _Vec3(4.0, 5.0, 7.8)

        out_pos, out_target = app._commit_camera_transform(cam_pos, target, center, 6.0)

        self.assertAlmostEqual(4.0, out_pos.x, places=4)
        self.assertAlmostEqual(-13.0, out_pos.y, places=4)
        self.assertAlmostEqual(16.0, out_pos.z, places=4)
        self.assertAlmostEqual(4.0, out_target.x, places=4)
        self.assertAlmostEqual(5.0, out_target.y, places=4)
        self.assertAlmostEqual(7.8, out_target.z, places=4)
        final_pos = app.camera.getPos()
        self.assertAlmostEqual(4.0, final_pos.x, places=4)
        self.assertAlmostEqual(-13.0, final_pos.y, places=4)
        self.assertAlmostEqual(16.0, final_pos.z, places=4)
        self.assertGreaterEqual(len(app.camera.look_targets), 1)


if __name__ == "__main__":
    unittest.main()
