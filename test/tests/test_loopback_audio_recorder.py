import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
LOOPBACK_RECORDER = (
    CODEX_HOME / "skills" / "record-gameplay-test-video" / "scripts" / "record_loopback_audio.py"
)
BLAS_THREAD_ENV_KEYS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "GOTO_NUM_THREADS",
)


class LoopbackAudioRecorderTests(unittest.TestCase):
    def test_recorder_limits_blas_threads_before_importing_numpy(self):
        self.assertTrue(
            LOOPBACK_RECORDER.exists(),
            f"Loopback recorder script not found: {LOOPBACK_RECORDER}",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "numpy.py").write_text(
                textwrap.dedent(
                    f"""\
                    import json
                    import os

                    print(json.dumps({{
                        {", ".join(f'"{key}": os.environ.get("{key}")' for key in BLAS_THREAD_ENV_KEYS)}
                    }}))

                    def fromstring(*args, **kwargs):
                        return b""
                    """
                ),
                encoding="utf-8",
            )
            (tmp_path / "soundcard.py").write_text("", encoding="utf-8")

            env = os.environ.copy()
            for key in BLAS_THREAD_ENV_KEYS:
                env.pop(key, None)

            extra_pythonpath = str(tmp_path)
            if env.get("PYTHONPATH"):
                env["PYTHONPATH"] = extra_pythonpath + os.pathsep + env["PYTHONPATH"]
            else:
                env["PYTHONPATH"] = extra_pythonpath

            completed = subprocess.run(
                [sys.executable, str(LOOPBACK_RECORDER)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(
                0,
                completed.returncode,
                "Recorder import probe should exit via argparse because no CLI arguments were supplied.",
            )
            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            self.assertTrue(stdout_lines, f"Expected fake numpy import probe output. stderr:\n{completed.stderr}")
            payload = json.loads(stdout_lines[0])

        self.assertEqual({key: "1" for key in BLAS_THREAD_ENV_KEYS}, payload)


if __name__ == "__main__":
    unittest.main()
