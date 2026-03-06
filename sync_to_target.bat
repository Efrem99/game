@echo off
setlocal

if not "%GAME_SYNC_TARGET%"=="" (
  python scripts\sync_to_target.py --target "%GAME_SYNC_TARGET%" %*
) else (
  python scripts\sync_to_target.py %*
)

endlocal
