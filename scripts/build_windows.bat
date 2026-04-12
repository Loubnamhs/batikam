@echo off
setlocal

set VERSION=1.0.0
if not "%~1"=="" set VERSION=%~1

echo.
echo  =========================================
echo   Batikam Renove — Build Windows v%VERSION%
echo  =========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass ^
    -File "%~dp0build_windows.ps1" ^
    -Version "%VERSION%"

if errorlevel 1 (
    echo.
    echo  ERREUR : le build a echoue.
    pause
    exit /b 1
)

echo.
echo  Build termine avec succes.
pause
endlocal
