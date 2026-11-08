@echo off
REM Starts CampusHub at http://localhost:8010 using the project's own "venv".
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
    echo The virtual environment "venv" is missing. Run setup.bat first.
    pause
    exit /b 1
)
echo CampusHub is starting at http://localhost:8010  (press Ctrl+C to stop)
venv\Scripts\python.exe manage.py runserver 8010
pause
