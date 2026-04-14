import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from render.magic_vfx import MagicVFXSystem


class _NodeStub:
    def __init__(self):
        self.removed = False

    def isEmpty(self):
        return bool(self.removed)

    def removeNode(self):
        self.removed = True


class _TaskStub:
    def __init__(self):
        self.done_calls = 0

    def done(self):
        self.done_calls += 1
        return "task-done-token"


class _Harness:
    _cleanup_node = MagicVFXSystem._cleanup_node
    _build_cleanup_task_callback = MagicVFXSystem._build_cleanup_task_callback


class MagicVfxTaskCleanupTests(unittest.TestCase):
    def test_cleanup_node_invokes_task_done_method(self):
        harness = _Harness()
        node = _NodeStub()
        task = _TaskStub()

        result = harness._cleanup_node(node, task)

        self.assertTrue(node.removed)
        self.assertEqual("task-done-token", result)
        self.assertEqual(1, task.done_calls)

    def test_cleanup_task_callback_runs_particle_cleanup_and_returns_task_done(self):
        harness = _Harness()
        node = _NodeStub()
        task = _TaskStub()
        cleanup_calls = []

        callback = harness._build_cleanup_task_callback(lambda: cleanup_calls.append("cleanup"), node)
        result = callback(task)

        self.assertEqual(["cleanup"], cleanup_calls)
        self.assertTrue(node.removed)
        self.assertEqual("task-done-token", result)
        self.assertEqual(1, task.done_calls)

    def test_cleanup_task_callback_can_finish_without_node(self):
        harness = _Harness()
        task = _TaskStub()
        cleanup_calls = []

        callback = harness._build_cleanup_task_callback(lambda: cleanup_calls.append("cleanup"), None)
        result = callback(task)

        self.assertEqual(["cleanup"], cleanup_calls)
        self.assertEqual("task-done-token", result)
        self.assertEqual(1, task.done_calls)


if __name__ == "__main__":
    unittest.main()
