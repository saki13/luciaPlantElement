@echo off
rem ---------------------------------------------------------------
rem  Start the Plant Art Forge over a local http server.
rem  Use this if saving does not work when opening index.html directly
rem  (Safari blocks storage on file:// URLs).
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY=D:\ProgramData\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

echo [forge] python = %PY%
echo [forge] starting local server, a browser tab will open ...
echo.

"%PY%" serve.py
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo [forge] exiting with code %CODE%
  pause
)
endlocal
