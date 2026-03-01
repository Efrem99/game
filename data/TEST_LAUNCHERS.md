# Test Launchers

Feature-specific test launchers:

- `python launcher_test_dragon.py`
- `python launcher_test_music.py`
- `python launcher_test_journal.py`
- `python launcher_test_mounts.py`
- `python launcher_test_skills.py`
- `python launcher_test_manifest.py` (checks `data/actors/player_animations.json` integrity)
- `python launcher_test_baseline.py` (prints static project baseline metrics)

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

You can also pass custom coordinates via env var:

- `XBOT_TEST_LOCATION=\"x,y,z\"`
