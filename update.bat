@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
 echo Run install.bat before updating.
 echo Press any key to continue . . .
pause >nul
 exit /b 1
)
echo Close zPrompt Studio before continuing.
echo Press any key to continue . . .
pause >nul
"venv\Scripts\python.exe" scripts\update.py
set "UPDATE_RESULT=%ERRORLEVEL%"
echo Press any key to continue . . .
pause >nul
exit /b %UPDATE_RESULT%
