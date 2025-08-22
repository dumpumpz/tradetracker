@echo OFF
TITLE TradeTracker Local Data Updater (DIAGNOSTIC MODE)
cd /D "%~dp0"
cls

echo ===========================================
echo      TRADETACKER LOCAL DATA UPDATER
echo ===========================================
echo.

:: --- STEP 1: CHECK FOR PYTHON VIRTUAL ENVIRONMENT ---
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [!] Python virtual environment not found.
    echo [*] Creating a new virtual environment...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo [!!!] FATAL ERROR: Failed to create the virtual environment.
        echo     Please ensure Python is installed and added to your PATH.
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
echo [1/4] Activating Python virtual environment...
call "venv\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: Could not activate the virtual environment.
    goto:error_exit
)
echo.

:: --- STEP 3: RUN PYTHON ANALYSIS SCRIPTS ---
echo [2/4] Running Moving Average analysis script...
python generate_accurate_ma.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Moving Average script failed.
    goto:error_exit
)
echo.

echo [3/4] Running Support/Resistance analysis script...
python sr_levels_analysis.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The S/R script failed.
    goto:error_exit
)
echo.

:: --- STEP 4: COMMIT AND PUSH CHANGES TO GITHUB ---
echo [4/4] Committing and pushing data to GitHub...
echo.

REM Add the JSON files AND force add the cache directory, overriding the .gitignore.
git add -f ma_analysis.json sr_levels_analysis.json market_opens.json warmup_ohlc_data_fixed/
IF ERRORLEVEL 1 (
    echo [!] WARNING: 'git add' command failed.
)

REM Commit the changes with a standard message
REM The '|| exit /b 0' part will exit gracefully if there are no changes to commit
git diff-index --quiet HEAD -- || git commit -m "Automated local data update"

REM ======================== VITAL DIAGNOSTIC STEP ========================
echo.
echo [DEBUG] The commit has finished. Now checking the status right before the pull.
echo [DEBUG] If any files are listed below as "modified", that is the source of the error.
git status
echo.
echo [DEBUG] The script is paused. Please copy the text from the [DEBUG] lines above and paste it.
echo Press any key to continue to see the error again...
PAUSE >NUL
REM ======================================================================

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
exit /b 0

:error_exit
echo.
echo Script encountered a fatal error and cannot continue.
echo This window will close in 20 seconds...
timeout /t 20 >nul
exit /b 1