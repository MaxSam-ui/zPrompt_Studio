@echo off
setlocal
cd /d "%~dp0"
title zPrompt Studio - Starting
echo ==============================================
echo zPrompt Studio - Starting
echo Folder: %CD%
echo ==============================================
if not exist "venv\Scripts\python.exe" (
 echo Run install.bat first.
 echo Press any key to continue . . .
pause >nul
 exit /b 1
)
echo Loading AI libraries and web interface...
echo The first startup may take some time. Keep this window open.
echo The browser will open when the server is ready.
echo.
"venv\Scripts\python.exe" -u main.py
set "APP_EXIT=%ERRORLEVEL%"
echo.
if not "%APP_EXIT%"=="0" echo Startup or execution failed. Exit code: %APP_EXIT%. Read the messages above.
if "%APP_EXIT%"=="0" echo zPrompt Studio stopped.
echo Press any key to continue . . .
pause >nul
exit /b %APP_EXIT%
