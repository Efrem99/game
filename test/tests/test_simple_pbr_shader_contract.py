import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERT_PATH = ROOT / "shaders" / "simple_pbr.vert"
FRAG_PATH = ROOT / "shaders" / "simple_pbr.frag"


def _shader_ios(path, qualifier):
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^\s*{qualifier}\s+(?:flat\s+|smooth\s+|noperspective\s+)?(?:lowp\s+|mediump\s+|highp\s+)?\w+\s+(\w+)\s*;",
        re.MULTILINE,
    )
    return set(pattern.findall(text))


class SimplePbrShaderContractTests(unittest.TestCase):
    def test_fragment_inputs_are_provided_by_vertex_outputs(self):
        vertex_outputs = _shader_ios(VERT_PATH, "out")
        fragment_inputs = _shader_ios(FRAG_PATH, "in")

        missing = sorted(fragment_inputs - vertex_outputs)

        self.assertEqual(
            [],
            missing,
            msg=(
                "simple_pbr.frag consumes varyings that simple_pbr.vert does not write: "
                f"{missing}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
