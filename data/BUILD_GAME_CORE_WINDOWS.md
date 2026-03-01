# Build `game_core.pyd` (Windows)

## Quick command

From project root:

```powershell
python scripts/build_game_core.py
```

Or:

```powershell
build.bat
```

## Requirements

1. Python 3.14+ (already used by project).
2. Visual Studio Build Tools with workload:
   - `Desktop development with C++`
3. Internet for first run (`pybind11` and `cmake` Python packages if missing).

## Expected result

File appears in project root:

- `game_core.pyd`

After that, startup warning
`game_core.pyd not found. Running in Python-only mode`
should disappear.

