@echo off
REM Quick start script for SDASystem (Windows)

echo ╔═══════════════════════════════════════════════════════════╗
echo ║       SDASystem v0.1 - Quick Start                        ║
echo ╚═══════════════════════════════════════════════════════════╝
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
if not exist "venv\.installed" (
    echo Installing dependencies...
    pip install -r requirements.txt
    type nul > venv\.installed
)

echo Note: Mock-data generation is NOT part of the default startup anymore.
echo If you need mock data, run: python scripts\generate_mock_data.py --force

echo.
echo Starting server...
echo.
echo Access the application at:
echo   -^> UI: http://localhost:8000/ui
echo   -^> API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the server
python main.py
