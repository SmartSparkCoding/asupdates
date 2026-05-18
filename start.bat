@echo off
REM AS Updates - Quick Start Script (Windows)

echo ==================================
echo ^>^> AS Updates - Quick Start
echo ==================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python is not installed
    exit /b 1
)

echo + Python found
echo.

REM Install dependencies
echo Package Manager: Installing dependencies...
python -m pip install -q Flask==3.0.0
python -m pip install -q Flask-Session==0.5.0
python -m pip install -q APScheduler==3.10.4
python -m pip install -q python-dotenv==1.0.0
python -m pip install -q Werkzeug==3.0.0
python -m pip install -q pytz==2024.1
echo + Dependencies installed
echo.

REM Check if .env exists
if not exist .env (
    echo Text: .env file not found
    if exist .env.example (
        echo Sheet: Creating .env from .env.example...
        copy .env.example .env
        echo + .env created
        echo.
        echo ! IMPORTANT: Edit .env and set:
        echo   - ADMIN_PASSWORD: Change to your password
        echo   - GMAIL_USER: (optional for email^)
        echo   - GMAIL_APP_PASSWORD: (optional for email^)
        echo.
        echo Then run this script again or start the app with:
        echo   python app.py
        exit /b 0
    ) else (
        echo X .env.example not found
        exit /b 1
    )
) else (
    echo + .env file found
)

echo.
echo ==================================
echo Goal: Starting AS Updates
echo ==================================
echo.
echo Location: Access the app at http://localhost:5000
echo.
echo Lock: Admin Password: (check your .env file^)
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the Flask app
python app.py

pause
