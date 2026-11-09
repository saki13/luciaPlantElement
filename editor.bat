@echo off
rem ---------------------------------------------------------------
rem  Plant Forge editor - draw / generate / replace plant art
rem  Double-click to launch the Tkinter GUI editor.
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0anim_demo"

set "PY=D:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo [editor] python = %PY%
echo [editor] launching Plant Forge ...

"%PY%" plant_editor.py
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo [editor] exited with code %CODE%
  pause
)
endlocal
