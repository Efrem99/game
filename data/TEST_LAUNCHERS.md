# Test Launchers

Primary launcher entry:

- `launcher_tests.pyw` (single executable launcher for all tests, opens Test Hub menu)

CLI equivalents:

- `python launcher_test_hub.py` (single launcher with menu and `--test` / `--list`)
- `python launchers/tests/launcher_test_dragon.py`
- `python launchers/tests/launcher_test_music.py`
- `python launchers/tests/launcher_test_journal.py`
- `python launchers/tests/launcher_test_mounts.py`
- `python launchers/tests/launcher_test_skills.py`
- `python launchers/tests/launcher_test_movement.py`
- `python launchers/tests/launcher_test_parkour.py`
- `python launchers/tests/launcher_test_flight.py`
- `python launchers/tests/launcher_test_manifest.py` (checks `data/actors/player_animations.json` integrity)
- `python launchers/tests/launcher_test_player_anim_runtime.py` (checks runtime state->clip resolution and T-pose risk)
- `python launchers/tests/launcher_test_baseline.py` (prints static project baseline metrics)
- `python launchers/tests/launcher_test_smoke.py` (runs static smoke checks + preflight reports)
- `python launchers/tests/launcher_test_sherward.py` (validates Shervard hero asset slot/config/docs)
- `python launchers/tests/launcher_test_sherward_prep.py` (builds first-pass Shervard asset via Blender or placeholder copy)

Legacy `launcher_test_*.pyw` wrappers were removed; use `launcher_tests.pyw` as the single executable test entry point.

Useful hub examples:

- `python launcher_test_hub.py --list`
- `python launcher_test_hub.py --test prototype_v1`
- `python launcher_test_hub.py --test parkour`
- `python launcher_test_hub.py --test voice_report`
- `python scripts/voice_dialog_report.py --synthesize-all --force-regenerate --engine speech`
- `python scripts/voice_dialog_report.py --synthesize-missing --engine speech --dry-run-synthesis`

Each launcher sets:

- `XBOT_TEST_PROFILE`
- `XBOT_TEST_LOCATION`

Profiles are applied in `src/app.py` after world/player initialization.

Supported location presets:

- `town`
- `castle`
- `docks`
- `dragon_arena`
- `boats`
- `training` / `training_grounds`
- `parkour`
- `flight`
- `prototype_v1`

You can also pass custom coordinates via env var:

- `XBOT_TEST_LOCATION=\"x,y,z\"`

