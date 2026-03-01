@echo off
setlocal
cd /d "%~dp0"

set "PYW="
for /d %%D in ("%LocalAppData%\Python\pythoncore-*") do (
    if exist "%%~fD\pythonw.exe" set "PYW=%%~fD\pythonw.exe"
)

if defined PYW (
    "%PYW%" "run_game.pyw"
) else (
    pythonw "run_game.pyw"
)

endlocal
