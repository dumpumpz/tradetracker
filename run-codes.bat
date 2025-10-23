@echo off
TITLE TradeTracker - Full Analysis and GitHub Push
CLS

REM =================================================================
REM      CONFIGURATION
REM =================================================================
SET REMOTE_NAME=origin
SET BRANCH_NAME=main
SET COMMIT_MESSAGE=Automated data update

REM =================================================================
REM      MAIN SCRIPT LOGIC
REM =================================================================
echo ===========================================
echo      TRADETRACKER ANALYSIS & GITHUB PUSHER
echo ===========================================
echo.

:: --- STEP 1: NAVIGATE TO SCRIPT DIRECTORY ---
:: This makes the script portable and ensures it runs in the correct folder.
cd /D "%~dp0"

:: --- STEP 2: SETUP/ACTIVATE PYTHON VIRTUAL ENVIRONMENT ---
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [!] Python virtual environment not found.
    echo [*] Creating a new virtual environment...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo [!!!] FATAL ERROR: Failed to create the virtual environment. Make sure Python is installed and in your PATH.
        goto:error_exit
    )
    echo [*] Installing required packages from requirements.txt...
    call "venv\Scripts\activate.bat"
    pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo [!!!] FATAL ERROR: Failed to install required packages. Check your requirements.txt file.
        goto:error_exit
    )
    echo.
)
echo [*] Activating Python virtual environment...
call "venv\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: Could not activate the virtual environment.
    goto:error_exit
)
echo.

:: --- STEP 3: RUN PYTHON ANALYSIS SCRIPTS ---
echo [>>] Running Moving Average analysis script...
python generate_accurate_ma.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Moving Average script failed.
    goto:error_exit
)
echo.

echo [>>] Running Support/Resistance analysis script...
python sr_levels_analysis.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The S/R script failed.
    goto:error_exit
)
echo.

echo [>>] Running S-Signal analysis script...
python s_signal_analysis.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The S-Signal script failed.
    goto:error_exit
)
echo.

echo [>>] Running Volume Profile analysis script...
python volume-profile.py
IF ERRORLEVEL 1 (
    echo [!!!] FATAL ERROR: The Volume Profile script failed.
    goto:error_exit
)
echo.

:: --- STEP 4: PUSH DATA TO GITHUB (ROBUST METHOD) ---
echo ===========================================
echo      COMMITTING AND PUSHING TO GITHUB
echo ===========================================
echo.

ECHO [*] Staging all new and modified files...
git add .

ECHO [*] Checking for changes to commit...
git diff-index --quiet HEAD --
IF ERRORLEVEL 1 (
    ECHO [*] Changes detected. Committing with a timestamp...
    
    REM Use PowerShell for a clean, sortable timestamp (YYYY-MM-DD HH:mm:ss)
    FOR /f "tokens=*" %%g IN ('powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"') do (SET "TIMESTAMP=%%g")

    git commit -m "%COMMIT_MESSAGE%: %TIMESTAMP%"
    IF ERRORLEVEL 1 (
        ECHO [!!!] FATAL ERROR: 'git commit' failed. Check for commit hooks or other issues.
        goto:error_exit
    )
) ELSE (
    ECHO [*] No changes to commit. The local repository is already up-to-date.
)

ECHO.
ECHO [*] Pulling latest changes from the remote repository to avoid conflicts...
REM Using --rebase avoids unnecessary merge commits in the history.
git pull --rebase %REMOTE_NAME% %BRANCH_NAME%
IF ERRORLEVEL 1 (
    ECHO [!!!] FATAL ERROR: 'git pull --rebase' failed. A manual merge is required.
    ECHO [!!!] Open a terminal in this folder and run 'git status' to see how to fix it.
    goto:error_exit
)

ECHO.
ECHO [*] Pushing your local commits to the online repository...
git push %REMOTE_NAME% %BRANCH_NAME%
IF ERRORLEVEL 1 (
    ECHO [!] WARNING: 'git push' failed. This is often normal if there were no new local commits to push.
)

ECHO.
echo ===========================================
echo      (^_^) ALL PROCESSES COMPLETE!
echo ===========================================
echo.
echo This window will close in 15 seconds...
timeout /t 15 /nobreak >nul
exit /b 0

:error_exit
ECHO.
ECHO [!!!] SCRIPT ENCOUNTERED A FATAL ERROR AND CANNOT CONTINUE.
ECHO [!!!] Please review the error messages above.
echo.
pause
exit /b 1