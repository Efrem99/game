import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from managers.dialog_cinematic_manager import DialogCinematicManager
from managers.npc_interaction_manager import NPCInteractionManager


class _Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)


class _LensStub:
    def project(self, _p3d, p2d):
        p2d.set(0.25, 0.5)
        return True


class _CameraNodeStub:
    def getLens(self):
        return _LensStub()


class _TransformGuardNode:
    def __init__(self, pos=None, scale=None, hpr=None):
        self._pos = pos or _Vec(0.0, 0.0, 0.0)
        self._scale = scale or _Vec(1.0, 1.0, 1.0)
        self._hpr = hpr or _Vec(0.0, 0.0, 0.0)

    def isEmpty(self):
        return False

    def getPos(self, *_):
        return self._pos

    def getScale(self, *_):
        return self._scale

    def getHpr(self, *_):
        return self._hpr

    def getTransform(self, *_):
        raise AssertionError("has_mat() should not be touched")

    def getRelativePoint(self, _other, point):
        return point


class _DialogActorStub(_TransformGuardNode):
    pass


class _TaskMgrStub:
    def doMethodLater(self, *_args, **_kwargs):
        return None

    def remove(self, *_args, **_kwargs):
        return None


class _VisibilityStub:
    def __init__(self, hidden=False):
        self._hidden = bool(hidden)

    def isHidden(self):
        return bool(self._hidden)

    def show(self):
        self._hidden = False

    def hide(self):
        self._hidden = True


class _CameraDirectorStub:
    def __init__(self):
        self.anchor_calls = []
        self.basic_calls = []

    def play_anchor_camera_shot(self, **kwargs):
        self.anchor_calls.append(dict(kwargs))
        return True

    def play_camera_shot(self, *args, **kwargs):
        self.basic_calls.append((args, dict(kwargs)))
        return True


class NPCDialogTransformGuardTests(unittest.TestCase):
    def test_world_to_screen_projects_without_touching_transformstate_matrix(self):
        mgr = NPCInteractionManager.__new__(NPCInteractionManager)
        camera = _TransformGuardNode()
        render = _TransformGuardNode()
        mgr.app = SimpleNamespace(
            camera=camera,
            render=render,
            cam=SimpleNamespace(node=lambda: _CameraNodeStub()),
            getAspectRatio=lambda: 2.0,
        )

        screen_pos = mgr._world_to_screen(Vec3(1.0, 2.0, 3.0))

        self.assertEqual((0.5, 0.5), screen_pos)

    def test_on_interact_starts_dialogue_without_nodepath_has_mat_guard(self):
        started = {}

        def _start_dialogue(**kwargs):
            started.update(kwargs)

        mgr = NPCInteractionManager.__new__(NPCInteractionManager)
        mgr._nearest_id = "merchant_general"
        mgr._units = {
            "merchant_general": {
                "actor": _DialogActorStub(),
                "dialogue_path": "merchant_general",
                "name": "Merchant",
            }
        }
        mgr._load_dialogue = lambda _path: {"dialogue_tree": {"start": {}}}
        mgr.app = SimpleNamespace(
            dialog_cinematic=SimpleNamespace(
                is_active=lambda: False,
                start_dialogue=_start_dialogue,
            ),
            state_mgr=SimpleNamespace(current_state="PLAYING"),
            GameState=SimpleNamespace(PLAYING="PLAYING"),
        )

        mgr._on_interact()

        self.assertEqual("merchant_general", started.get("npc_id"))
        self.assertIs(started.get("npc_actor"), mgr._units["merchant_general"]["actor"])

    def test_dialog_cinematic_start_dialogue_accepts_actor_without_has_mat_probe(self):
        accepted = []
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = SimpleNamespace(
            taskMgr=_TaskMgrStub(),
            accept=lambda event_name, _fn: accepted.append(event_name),
            ignore=lambda _event_name: None,
            aspect2d=_VisibilityStub(hidden=False),
        )
        mgr._active = False
        mgr._sequence = None
        mgr._ui_nodes = []
        mgr._choice_btns = []
        mgr._current_node = None
        mgr._dialogue_data = None
        mgr._npc_actor = None
        mgr._npc_id = ""
        mgr._on_end = None
        mgr._cam_target_pos = None
        mgr._cam_target_look = None
        mgr._cam_blend_t = 0.0
        mgr._can_advance = False
        mgr._advance_queued = False
        mgr._bar_top = None
        mgr._bar_bot = None
        mgr._sub_bg = None
        mgr._sub_text = None
        mgr._spk_text = None
        mgr._bars_built = False
        mgr._build_ui = lambda: None
        mgr._enter_dialog_state = lambda: None
        mgr._play_bars_in = lambda: None
        mgr._task_start_node = lambda *_args, **_kwargs: None

        ok = mgr.start_dialogue(
            "merchant_general",
            {"dialogue_tree": {"start": {}}},
            npc_actor=_DialogActorStub(),
        )

        self.assertTrue(ok)
        self.assertIn("space", accepted)
        self.assertIn("e", accepted)

    def test_dialog_cinematic_temporarily_shows_hidden_aspect2d_for_subtitles(self):
        accepted = []
        aspect2d = _VisibilityStub(hidden=True)
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = SimpleNamespace(
            taskMgr=_TaskMgrStub(),
            accept=lambda event_name, _fn: accepted.append(event_name),
            ignore=lambda _event_name: None,
            aspect2d=aspect2d,
        )
        mgr._active = False
        mgr._sequence = None
        mgr._ui_nodes = []
        mgr._choice_btns = []
        mgr._current_node = None
        mgr._dialogue_data = None
        mgr._npc_actor = None
        mgr._npc_id = ""
        mgr._on_end = None
        mgr._cam_target_pos = None
        mgr._cam_target_look = None
        mgr._cam_blend_t = 0.0
        mgr._can_advance = False
        mgr._advance_queued = False
        mgr._bar_top = None
        mgr._bar_bot = None
        mgr._sub_bg = None
        mgr._sub_text = None
        mgr._spk_text = None
        mgr._bars_built = False
        mgr._dialog_ui_was_hidden = False
        mgr._build_ui = lambda: None
        mgr._enter_dialog_state = lambda: None
        mgr._play_bars_in = lambda: None
        mgr._task_start_node = lambda *_args, **_kwargs: None
        mgr._destroy_ui = lambda: None
        mgr._exit_dialog_state = lambda: None

        ok = mgr.start_dialogue(
            "merchant_general",
            {"dialogue_tree": {"start": {"text": "Hello"}}},
            npc_actor=_DialogActorStub(),
        )

        self.assertTrue(ok)
        self.assertFalse(aspect2d.isHidden())
        mgr._task_cleanup()
        self.assertTrue(aspect2d.isHidden())

    def test_dialog_camera_cut_frames_player_and_npc_pair_when_anchor_shot_is_available(self):
        cam_dir = _CameraDirectorStub()
        player_actor = _TransformGuardNode(pos=_Vec(0.0, 40.0, 0.0))
        npc_actor = _DialogActorStub(pos=_Vec(4.0, 46.0, 2.0))
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = SimpleNamespace(
            camera_director=cam_dir,
            player=SimpleNamespace(actor=player_actor),
            render=object(),
        )
        mgr._dialogue_data = {"npc_name": "Village Resident"}
        mgr._npc_actor = npc_actor

        mgr._do_camera_cut("Village Resident", "auto")

        self.assertEqual(1, len(cam_dir.anchor_calls))
        call = cam_dir.anchor_calls[0]
        self.assertEqual("dialog_npc", call.get("name"))
        self.assertAlmostEqual(2.0, float(call["center"].x), delta=0.001)
        self.assertAlmostEqual(43.0, float(call["center"].y), delta=0.001)
        self.assertAlmostEqual(4.0, float(call["look_target"].x), delta=0.001)
        self.assertAlmostEqual(46.0, float(call["look_target"].y), delta=0.001)
        self.assertEqual("dialog_pair", call.get("framing"))
        self.assertAlmostEqual(0.0, float(call["partner_target"].x), delta=0.001)
        self.assertAlmostEqual(40.0, float(call["partner_target"].y), delta=0.001)

    def test_dialog_camera_cut_marks_player_lines_for_pair_framing(self):
        cam_dir = _CameraDirectorStub()
        player_actor = _TransformGuardNode(pos=_Vec(1.0, 32.0, 0.0))
        npc_actor = _DialogActorStub(pos=_Vec(4.0, 35.0, 0.5))
        mgr = DialogCinematicManager.__new__(DialogCinematicManager)
        mgr.app = SimpleNamespace(
            camera_director=cam_dir,
            player=SimpleNamespace(actor=player_actor),
            render=object(),
        )
        mgr._dialogue_data = {"npc_name": "Village Resident"}
        mgr._npc_actor = npc_actor

        mgr._do_camera_cut("Traveler", "player")

        self.assertEqual(1, len(cam_dir.anchor_calls))
        call = cam_dir.anchor_calls[0]
        self.assertEqual("dialog_player", call.get("name"))
        self.assertEqual("dialog_pair", call.get("framing"))
        self.assertAlmostEqual(1.0, float(call["look_target"].x), delta=0.001)
        self.assertAlmostEqual(32.0, float(call["look_target"].y), delta=0.001)
        self.assertAlmostEqual(4.0, float(call["partner_target"].x), delta=0.001)
        self.assertAlmostEqual(35.0, float(call["partner_target"].y), delta=0.001)


if __name__ == "__main__":
    unittest.main()
