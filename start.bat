@echo off
chcp 65001 >nul
title Ahdaf Proposal Generator
cd /d "%~dp0"

rem ---- find Python 3.10+
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
if not defined PY (
  echo Python 3.10+ is required. Install it from https://www.python.org/downloads/ then run this file again.
  pause
  exit /b 1
)

rem ---- install dependencies on first run
if not exist "data\.deps-ok" (
  echo Installing requirements, first run only...
  %PY% -m pip install -q -r requirements.txt || (echo Failed to install requirements & pause & exit /b 1)
  if not exist data mkdir data
  echo ok> "data\.deps-ok"
)

rem ---- open the browser shortly after the server starts
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8765"
%PY% -m app
pause
