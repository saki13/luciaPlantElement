@echo off
rem ---------------------------------------------------------------
rem  PVZ-like launcher (M5 "I am Zombie" mode: inverted attack/defense)
rem  Double-click to play.
rem  ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PYTHONPATH=%~dp0libs;%~dp0"

set "PY=D:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo [launcher] python = %PY%
echo [launcher] mode   = izombie

"%PY%" -m tdgame.app_pygame --mode izombie %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo [launcher] exited with code %CODE%
  pause
)
endlocal
