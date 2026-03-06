@echo off
setlocal

if not "%XBOT_HTDOCS_TARGET%"=="" (
  python scripts\sync_to_htdocs.py --target "%XBOT_HTDOCS_TARGET%" %*
) else (
  python scripts\sync_to_htdocs.py %*
)

endlocal
