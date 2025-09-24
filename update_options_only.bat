@echo OFF
TITLE TradeTracker Options Data Updater
cd /D "%~dp0"
cls

echo ===========================================
echo      TRADETRACKER OPTIONS DATA UPDATER
echo ===========================================
echo.

:: --- STEP 1: CHECK FOR PYTHON VIRTUAL ENVIRONMENT ---
:: This check is important to ensure the script can run independently
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [!] Python virtual environment not found.
    echo [*] Creating a new virtual environment...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo [!!!] FATAL ERROR: Failed to create the virtual environment.
        goto:error_exit
    )
    echo [*] Installing required packages from requirements.txt...
    call "venv\Scripts\activate.bat"
    pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo [!!!] FATAL ERROR: Failed to install required packages.
        goto:error_exit
    )
    echo.
)

:: --- STEP 2: ACTIVATE VIRTUAL ENVIRONMENT ---
echo [1/2] Activating Python virtual environment...
call "venv\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: Could not activate the virtual environment.
    goto:error_exit
)
echo.

:: --- STEP 3: RUN OPTIONS ANALYSIS SCRIPT ---
echo [2/2] Running Options Open Interest script...
python option-open-interest-json.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Options OI script failed.
    goto:error_exit
)
echo.

echo ===========================================
echo      (^_^) OPTIONS UPDATE PROCESS COMPLETE!
echo ===========================================
echo.
echo This window will close in 10 seconds...
timeout /t 10 >nul
exit /b 0

:error_exit
echo.
echo Script encountered a fatal error and cannot continue.
echo Press any key to close this window...
pause >nul
exit /b 1