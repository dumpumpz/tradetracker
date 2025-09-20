@echo OFF
TITLE TradeTracker Local Data Updater
cd /D "%~dp0"
cls

echo ===========================================
echo      TRADETRACKER LOCAL DATA UPDATER
echo ===========================================
echo.

:: --- STEP 1: CHECK FOR PYTHON VIRTUAL ENVIRONMENT ---
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
echo [1/7] Activating Python virtual environment...
call "venv\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: Could not activate the virtual environment.
    goto:error_exit
)
echo.

:: --- STEP 3: RUN PYTHON ANALYSIS SCRIPTS ---
echo [2/7] Running Moving Average analysis script...
python generate_accurate_ma.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Moving Average script failed.
    goto:error_exit
)
echo.

echo [3/7] Running Support/Resistance analysis script...
python sr_levels_analysis.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The S/R script failed.
    goto:error_exit
)
echo.

echo [4/7] Running S-Signal analysis script...
python s_signal_analysis.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The S-Signal script failed.
    goto:error_exit
)
echo.

echo [5/7] Running Options Open Interest script...
python option-open-interest-json.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Options OI script failed.
    goto:error_exit
)
echo.

echo [6/7] Running Volume Profile analysis script...
python volume-profile.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Volume Profile script failed.
    goto:error_exit
)
echo.

:: --- STEP 4: COMMIT AND PUSH CHANGES TO GITHUB ---
echo [7/7] Committing and pushing data to GitHub...
echo.

REM Add ALL new and modified files in the project to the staging area.
git add .
IF ERRORLEVEL 1 (
    echo [!] WARNING: 'git add' command failed.
)

REM Commit the changes with a standard message if there are changes
git diff-index --quiet HEAD -- || git commit -m "Automated local data update"

echo [*] Pulling latest changes from the remote repository...
git pull --rebase
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: 'git pull --rebase' failed. A manual merge might be needed.
    goto:error_exit
)

echo [*] Pushing local commits to the remote repository...
git push
IF ERRORLEVEL 1 (
    echo [!] WARNING: 'git push' failed. This is often normal if the remote was already up-to-date.
)
echo.

echo ===========================================
echo      (O_O) UPDATE PROCESS COMPLETE!
echo ===========================================
echo.
echo This window will close in 10 seconds...
timeout /t 10 >nul
PAUSE REM <<< ADD THIS LINE
exit /b 0

:error_exit
echo.
echo Script encountered a fatal error and cannot continue.
echo This window will close in 20 seconds...
timeout /t 20 >nul
PAUSE REM <<< ADD THIS LINE
exit /b 1