from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def test_runtime_vehicle_policy_skips_non_mount_test_profiles():
    source = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    start = source.index("    def _should_spawn_default_runtime_vehicles(self):")
    end = source.index("    def _should_skip_runtime_roster_spawns(self):", start)
    block = source[start:end]

    assert 'profile = self._norm_test_mode()' in block
    assert 'if profile and profile != "mounts":' in block
    assert "return False" in block
