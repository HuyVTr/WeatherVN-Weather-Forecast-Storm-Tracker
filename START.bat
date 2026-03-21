@echo off
cls

echo =============================================================
echo. 
echo           CHU TRINH DU BAO BAO TU DONG
echo.
echo =============================================================
pause

:MAIN_MENU
cls
echo.
echo =============================================================
echo.
echo      CHON CHUC NANG KHOI DONG HE THONG
echo.
echo =============================================================
echo.
echo   1. Khoi dong HE THONG DU BAO LIEN TUC + Web Server
echo   2. Chay DU BAO REAL-TIME mot lan + Khoi dong Web Server
echo   3. Chay HUAN LUYEN NHANH (Quick Train)
echo   4. Chay HUAN LUYEN DAY DU (Full Train)
echo   5. Chay mo phong BAO RAI (Typhoon Rai) va khoi dong Web Server
echo   6. Thoat
echo.

CHOICE /C 123456 /M "Ban chon cach nao?"

IF ERRORLEVEL 6 GOTO END_SCRIPT
IF ERRORLEVEL 5 GOTO RUN_RAI_SIMULATION_AND_SERVER
IF ERRORLEVEL 4 GOTO RUN_FULL_TRAIN
IF ERRORLEVEL 3 GOTO RUN_QUICK_TRAIN
IF ERRORLEVEL 2 GOTO RUN_ONE_TIME_REALTIME_AND_SERVER
IF ERRORLEVEL 1 GOTO START_CONTINUOUS_FORECAST_AND_SERVER


:START_CONTINUOUS_FORECAST_AND_SERVER
cls
echo ">> KHOI DONG HE THONG DU BAO LIEN TUC (trong cua so moi)..."
start "Final Storm Forecast - CONTINUOUS" cmd /k "call "%~dp0venv\Scripts\activate" && cd /d "%~dp0" && "%~dp0venv\Scripts\python.exe" -m services.storm_prediction_service.final_storm_forecast 3.2 --device cuda"
timeout /t 5 >nul
echo ">> KHOI DONG WEB SERVER (trong cua so moi)..."
start "Web Server (Port 8000)" cmd /k "call "%~dp0venv\Scripts\activate" && cd /d "%~dp0" && python -u app.py"
GOTO END_PROMPT

:RUN_ONE_TIME_REALTIME_AND_SERVER
cls
echo ">> CHAY DU BAO REAL-TIME MOT LAN..."
call "%~dp0venv\Scripts\activate"
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m services.storm_prediction_service.final_storm_forecast 3.1 --device cuda
echo ">> DU BAO REAL-TIME HOAN TAT. KHOI DONG WEB SERVER..."
start "Web Server (Port 8000)" cmd /k "call "%~dp0venv\Scripts\activate" && cd /d "%~dp0" && python -u app.py"
GOTO END_PROMPT

:RUN_QUICK_TRAIN
cls
echo ">> CHAY HUAN LUYEN NHANH (QUICK TRAIN)..."
call "%~dp0venv\Scripts\activate"
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m services.storm_prediction_service.final_storm_forecast 1 --device cuda
echo ">> HUAN LUYEN NHANH HOAN TAT."
pause
GOTO MAIN_MENU

:RUN_FULL_TRAIN
cls
echo ">> CHAY HUAN LUYEN DAY DU (FULL TRAIN)..."
call "%~dp0venv\Scripts\activate"
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m services.storm_prediction_service.final_storm_forecast 2 --device cuda
echo ">> HUAN LUYEN DAY DU HOAN TAT."
pause
GOTO MAIN_MENU

:RUN_RAI_SIMULATION_AND_SERVER
cls
echo ">> DANG TAO DU LIEU MO PHONG BAO RAI (TYPHOON RAI)..."
call "%~dp0venv\Scripts\activate"
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m services.storm_prediction_service.final_storm_forecast 3.3 --device cuda
echo ">> TAO DU LIEU MO PHONG HOAN TAT. KHOI DONG WEB SERVER..."
start "Web Server (Port 8000)" cmd /k "call "%~dp0venv\Scripts\activate" && cd /d "%~dp0" && python -u app.py"
GOTO END_PROMPT

:END_PROMPT
echo.
echo      -------------------------------------------------------
echo.
echo      [System] Cac lenh khoi dong da duoc thuc thi.
echo.
echo      [Link] Vui long mo trinh duyet va truy cap dia chi:
echo.
echo         http://127.0.0.1:8000 (neu web server duoc khoi dong)
echo.
echo      -------------------------------------------------------
echo.
pause
GOTO MAIN_MENU

:END_SCRIPT
echo.
echo "Da thoat. Tam biet!"
pause
exit
