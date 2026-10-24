@echo off
REM Build the Windows app. All steps are in build_windows.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
set BUILD_RESULT=%ERRORLEVEL%
REM Keep the window open when started by double-click, but not in CI.
if not defined CI pause
exit /b %BUILD_RESULT%
