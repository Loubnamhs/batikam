@echo off
setlocal

set VERSION=dev
if not "%~1"=="" set VERSION=%~1

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" -Version "%VERSION%"
if errorlevel 1 exit /b %errorlevel%

endlocal
