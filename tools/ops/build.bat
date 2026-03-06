@echo off
setlocal
cd /d "%~dp0"
echo [XBot RPG Ultimate] Building C++ Core...

python scripts\build_game_core.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed with code %errorlevel%.
    echo [HINT] Install Visual Studio Build Tools (Desktop development with C++).
    exit /b %errorlevel%
)

echo [SUCCESS] Build complete. game_core.pyd is in the project root.
endlocal
