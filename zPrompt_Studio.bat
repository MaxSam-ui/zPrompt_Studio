@echo off
setlocal
cd /d "%~dp0"
title zPrompt Studio - Starting
echo ==============================================
echo zPrompt Studio - Starting
echo Folder: %CD%
echo ==============================================
if not exist "venv\Scripts\python.exe" goto install
"venv\Scripts\python.exe" -c "import importlib.metadata as m; [m.version(x) for x in ['gradio','torch','transformers','accelerate','Pillow','requests']]" >nul 2>&1
if errorlevel 1 goto install
goto ready
:install
echo Installing application dependencies. Internet access is required.
call scripts\install.bat --from-start
if errorlevel 1 goto setup_failed
:ready
"venv\Scripts\python.exe" scripts\check_comfyui.py
echo Loading AI libraries and web interface...
echo The first startup may take some time. Keep this window open.
echo The browser will open when the server is ready.
echo.
"venv\Scripts\python.exe" -u scripts\main.py
set "APP_EXIT=%ERRORLEVEL%"
echo.
if not "%APP_EXIT%"=="0" echo Startup or execution failed. Exit code: %APP_EXIT%. Read the messages above.
if "%APP_EXIT%"=="0" echo zPrompt Studio stopped.
echo Press any key to continue . . .
pause >nul
exit /b %APP_EXIT%

:setup_failed
echo Installation failed. Review the messages above and retry.
pause
exit /b 1
