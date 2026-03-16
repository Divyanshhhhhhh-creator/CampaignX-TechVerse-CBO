@echo off
echo =======================================================
echo     CampaignX Multi-Agent System - Startup Script
echo =======================================================
echo.

echo [1/4] Installing Backend Dependencies...
cd backend
pip install -r requirements.txt

echo.
echo [2/4] Installing Frontend Dependencies...
cd ../frontend
call npm install

echo.
echo [3/4] Starting FastAPI Backend (Port 8000)...
cd ../backend
start "CampaignX Backend" cmd /k "python -m uvicorn main:app --reload"

echo.
echo [4/4] Starting Vite Frontend (Port 5173)...
cd ../frontend
start "CampaignX Frontend" cmd /k "npm run dev"

echo.
echo =======================================================
echo All services launched! 
echo Frontend: http://localhost:5173
echo Backend:  http://127.0.0.1:8000
echo =======================================================
cd ..
pause
