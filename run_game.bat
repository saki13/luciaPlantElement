@echo off
rem ---------------------------------------------------------------
rem  PVZ-like launcher (main campaign / playable client)
rem  Double-click to play. Extra args are forwarded, e.g.
rem      run_game.bat --smoke --frames 60      (headless smoke test)
rem      run_game.bat --level m3_05            (start at a level)
rem  ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

rem Use the project-bundled pygame first, then the repo itself.
set "PYTHONPATH=%~dp0libs;%~dp0"

rem Prefer the Anaconda interpreter this project was developed against.
set "PY=D:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo [launcher] python = %PY%
echo [launcher] mode   = play

"%PY%" -m tdgame.app_pygame %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo [launcher] exited with code %CODE%
  pause
)
endlocal
