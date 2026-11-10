@echo off
rem ---------------------------------------------------------------
rem  Plant Forge - HTML + Node editor (Windows)
rem  Double-click to start. Then open the printed URL in your browser.
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"
chcp 65001 >nul

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo  [!] Node.js not found.
  echo      Install the LTS version from https://nodejs.org/  then run this again.
  echo.
  pause
  exit /b 1
)

echo Starting Plant Forge ...
echo.
node server.js
echo.
echo [forge] stopped.
pause
endlocal
