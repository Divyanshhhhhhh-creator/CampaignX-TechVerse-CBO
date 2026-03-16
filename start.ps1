<#
.SYNOPSIS
    CampaignX - Multi-Agent System Startup Script
.DESCRIPTION
    Launches the FastAPI backend and Vite frontend concurrently.
#>

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "     CampaignX Multi-Agent System - Startup Script     " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Start Backend
Write-Host "[1/2] Starting Python/FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command `"cd backend; python -m pip install -r requirements.txt; python -m uvicorn main:app --reload --port 8000`""
Start-Sleep -Seconds 5

# 2. Start Frontend
Write-Host "[2/2] Starting React/Vite Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command `"cd frontend; npm install; npm run dev`""

Write-Host ""
Write-Host "✅ Both services are booting up in the background." -ForegroundColor Green
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host "   Backend API: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop the servers, close this PowerShell window." -ForegroundColor Gray
