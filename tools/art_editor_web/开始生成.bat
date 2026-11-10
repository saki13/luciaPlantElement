@echo off
rem ---------------------------------------------------------------
rem  Plant Art Studio - generate images locally (Windows)
rem  Just double-click this file.
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo  [!] Python not found.
  echo      Install it from https://www.python.org/downloads/windows/
  echo      During install, tick "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo Using Python: %PY%
%PY% --version
echo.

%PY% art_studio_cli.py %*
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (
  echo [exit code: %CODE%]
  echo If it failed, read 说明.md  ^>  "常见问题"
) else (
  echo Done. Now go back to the web page and click "导入生成结果".
)
pause
endlocal
