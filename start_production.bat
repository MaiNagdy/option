@echo off
REM Production Start Script for Option Analytics (Windows)

echo ==========================================
echo 🚀 Starting Production Server
echo ==========================================

REM Set production environment variables
set APP_ENV=production
set HOST=0.0.0.0
set PORT=8000
set DEBUG=False
set ALLOWED_HOSTS=*
set CORS_ORIGINS=*

echo.
echo 🌐 Server will be accessible at:
echo    - Local: http://localhost:8000
echo    - Network: http://YOUR_LOCAL_IP:8000
echo    - External: http://YOUR_PUBLIC_IP:8000
echo.
echo ✅ All features enabled:
echo    - Full Profile Access
echo    - Unlimited Analysis
echo    - CSV Export
echo    - All Valuation Models
echo.
echo ==========================================
echo.

REM Install dependencies if needed
if not exist "venv" (
    echo 📦 Installing dependencies...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Start the application
python app.py

pause

