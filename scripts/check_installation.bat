@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
 echo Run scripts\install.bat first.
 echo Press any key to continue . . .
pause >nul
 exit /b 1
)
"venv\Scripts\python.exe" -u services\installation_check.py
set "CHECK_EXIT=%ERRORLEVEL%"
echo Press any key to continue . . .
pause >nul
exit /b %CHECK_EXIT%
