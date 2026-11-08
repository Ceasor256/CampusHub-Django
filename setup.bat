@echo off
REM One-time setup: creates the "venv" virtual environment, installs packages,
REM builds the database and loads sample data. Safe to run again.
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
    echo Creating virtual environment "venv"...
    python -m venv venv || goto :error
)
echo Installing packages into venv...
venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt || goto :error
echo Setting up the database...
venv\Scripts\python.exe manage.py migrate || goto :error
venv\Scripts\python.exe manage.py seed || goto :error
echo.
echo Done. Double-click run.bat to start CampusHub.
pause
exit /b 0
:error
echo.
echo Setup failed. Read the message above.
pause
exit /b 1
