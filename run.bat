@echo off
title TRXC QRR Trading Terminal - Server
cd /d "%~dp0"
echo ========================================================
echo   TRXC QRR REAL-TIME TRADING TERMINAL
echo   Zero Repaint | Dual Signal | Pending Zones | Multi-TF
echo ========================================================
echo.
echo Memulai server backend dan live chart feed...
echo Buka browser pada: http://127.0.0.1:8000
echo.

start "" http://127.0.0.1:8000
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
) else (
    py -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
)
pause
