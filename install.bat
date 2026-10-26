@echo off
setlocal
cd /d "%~dp0"
echo Installing zPrompt Studio. Please keep this window open.
if not exist "settings.json" copy /Y "settings.example.json" "settings.json" >nul
py -3.11 --version >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.11 64-bit with the Python launcher, then retry.
 echo Press any key to continue . . .
pause >nul
 exit /b 1
)
if not exist "venv\Scripts\python.exe" py -3.11 -m venv venv
if errorlevel 1 goto failed
"venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
"venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
echo Dependencies installed. Checking environment and workflow requirements...
"venv\Scripts\python.exe" -u services\installation_check.py
if errorlevel 1 (
 echo Checks found errors. Review the report above before launching.
 echo Press any key to continue . . .
pause >nul
 exit /b 1
)
echo Installation finished. Resolve any CONFIG items for the features you need.
echo Repeat checks from Logs and Settings after starting ComfyUI.
echo Press any key to continue . . .
pause >nul
exit /b 0
:failed
echo Installation failed. Keep this window open to read the error above.
echo Press any key to continue . . .
pause >nul
exit /b 1
