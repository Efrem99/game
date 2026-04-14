import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app import XBotApp


class _TransformStub:
    def getMat(self):
        return "mat"


class _NodeStub:
    def __init__(self, name, children=None, invalid=False, invalid_mat=False):
        self._name = name
        self._children = list(children or [])
        self._invalid = bool(invalid)
        self._invalid_mat = bool(invalid_mat)
        self.detached = False

    def getChildren(self):
        return list(self._children)

    def isEmpty(self):
        return False

    def getName(self):
        return self._name

    def getMat(self, *_):
        if self._invalid_mat:
            raise AssertionError("has_mat()")
        return "mat"

    def getTransform(self, *_):
        if self._invalid:
            raise AssertionError("has_mat()")
        return _TransformStub()

    def getNetTransform(self):
        if self._invalid:
            raise AssertionError("has_mat()")
        return _TransformStub()

    def getPos(self, *_):
        return (0.0, 0.0, 0.0)

    def getScale(self, *_):
        return (1.0, 1.0, 1.0)

    def getHpr(self, *_):
        return (0.0, 0.0, 0.0)

    def detachNode(self):
        self.detached = True


class _AppSceneValidationDummy:
    _is_finite_components = XBotApp._is_finite_components
    _scene_node_debug_name = XBotApp._scene_node_debug_name
    _probe_scene_node_matrices = XBotApp._probe_scene_node_matrices
    _probe_scene_node_transform = XBotApp._probe_scene_node_transform
    _prune_invalid_scene_nodes = XBotApp._prune_invalid_scene_nodes
    _run_runtime_scene_guard = XBotApp._run_runtime_scene_guard
    _guard_runtime_scene_after_player_update = XBotApp._guard_runtime_scene_after_player_update

    def __init__(self, render):
        self.render = render
        self.camera = None
        self.render2d = None
        self.aspect2d = None
        self.player = None


class _GuardCaptureDummy:
    _collect_runtime_scene_guard_roots = XBotApp._collect_runtime_scene_guard_roots
    _guard_runtime_scene_with_label = XBotApp._guard_runtime_scene_with_label
    _guard_runtime_scene_after_player_update = XBotApp._guard_runtime_scene_after_player_update

    def __init__(self):
        self.render = _NodeStub("render_root")
        self.camera = _NodeStub("camera_root")
        self.render2d = _NodeStub("render2d_root")
        self.aspect2d = _NodeStub("aspect2d_root")
        self.pixel2d = _NodeStub("pixel2d_root")
        self.screen_quad = _NodeStub("screen_quad_root")
        self.player = type("PlayerHolder", (), {"actor": _NodeStub("player_actor")})()
        self.captured_roots = None

    def _run_runtime_scene_guard(self, roots=None):
        self.captured_roots = list(roots or [])
        return ["detached_bad"]


class _EnemyRosterRootsDummy:
    _collect_enemy_roster_scene_roots = XBotApp._collect_enemy_roster_scene_roots

    def __init__(self, roots):
        units = [type("EnemyUnit", (), {"root": root})() for root in roots]
        self.boss_manager = type("BossManagerHolder", (), {"units": units})()


class AppSceneValidationTests(unittest.TestCase):
    def test_prune_invalid_scene_nodes_detaches_bad_children(self):
        bad = _NodeStub("bad_node", invalid=True)
        good = _NodeStub("good_node")
        render = _NodeStub("render_root", children=[good, bad])
        app = _AppSceneValidationDummy(render)

        removed = app._prune_invalid_scene_nodes()

        self.assertEqual(["bad_node"], removed)
        self.assertFalse(good.detached)
        self.assertTrue(bad.detached)

    def test_runtime_scene_guard_defaults_to_render_root(self):
        bad = _NodeStub("bad_node", invalid=True)
        good = _NodeStub("good_node")
        render = _NodeStub("render_root", children=[good, bad])
        app = _AppSceneValidationDummy(render)

        removed = app._run_runtime_scene_guard()

        self.assertEqual(["bad_node"], removed)
        self.assertFalse(good.detached)
        self.assertTrue(bad.detached)

    def test_prune_invalid_scene_nodes_detaches_nodes_with_broken_local_matrix(self):
        bad = _NodeStub("bad_mat_node", invalid_mat=True)
        good = _NodeStub("good_node")
        render = _NodeStub("render_root", children=[good, bad])
        app = _AppSceneValidationDummy(render)

        removed = app._prune_invalid_scene_nodes()

        self.assertEqual(["bad_mat_node"], removed)
        self.assertFalse(good.detached)
        self.assertTrue(bad.detached)

    def test_post_player_scene_guard_scans_player_and_render_roots_once(self):
        app = _GuardCaptureDummy()

        removed = app._guard_runtime_scene_after_player_update()

        self.assertEqual(["detached_bad"], removed)
        self.assertIsNotNone(app.captured_roots)
        self.assertEqual(
            ["player_actor", "camera_root", "render_root", "render2d_root", "aspect2d_root", "pixel2d_root", "screen_quad_root"],
            [node.getName() for node in app.captured_roots],
        )

    def test_collect_runtime_scene_guard_roots_deduplicates_runtime_roots(self):
        app = _GuardCaptureDummy()

        roots = app._collect_runtime_scene_guard_roots()

        self.assertEqual(
            ["player_actor", "camera_root", "render_root", "render2d_root", "aspect2d_root", "pixel2d_root", "screen_quad_root"],
            [node.getName() for node in roots],
        )

    def test_guard_runtime_scene_with_label_uses_runtime_roots_by_default(self):
        app = _GuardCaptureDummy()

        removed = app._guard_runtime_scene_with_label("post_finalize")

        self.assertEqual(["detached_bad"], removed)
        self.assertEqual(
            ["player_actor", "camera_root", "render_root", "render2d_root", "aspect2d_root", "pixel2d_root", "screen_quad_root"],
            [node.getName() for node in app.captured_roots],
        )

    def test_collect_enemy_roster_scene_roots_deduplicates_and_skips_missing_roots(self):
        shared = _NodeStub("shared_enemy_root")
        unique = _NodeStub("unique_enemy_root")
        app = _EnemyRosterRootsDummy([shared, None, shared, unique])

        roots = app._collect_enemy_roster_scene_roots()

        self.assertEqual(
            ["shared_enemy_root", "unique_enemy_root"],
            [node.getName() for node in roots],
        )


if __name__ == "__main__":
    unittest.main()
