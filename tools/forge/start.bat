@echo off
rem ---------------------------------------------------------------
rem  Plant Forge - 网页版植物编辑器
rem  双击启动。有 Python 就用 Python，没有就用 Node。
rem ---------------------------------------------------------------
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)

if defined PY (
  echo [forge] 使用 Python 启动
  %PY% server.py
  goto done
)

where node >nul 2>nul
if not errorlevel 1 (
  echo [forge] 使用 Node 启动
  node server.js
  goto done
)

echo.
echo  [!] 这台机器上既没有 Python 也没有 Node。
echo      装任意一个都行（装完重开窗口再双击我）：
echo        Python: https://www.python.org/downloads/
echo        Node:   https://nodejs.org/
echo.
pause
exit /b 1

:done
echo.
echo [forge] 已停止。
pause
endlocal
