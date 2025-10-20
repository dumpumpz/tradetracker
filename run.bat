@echo off
TITLE TradeTracker Data Pusher - Robust Version

REM =================================================================
REM      CONFIGURATION
REM =================================================================
SET REPO_PATH="C:\Users\River\tradetracker"
SET REMOTE_NAME=origin
SET BRANCH_NAME=main
SET COMMIT_MESSAGE=Automated data update

REM =================================================================
REM      GIT AUTOMATION SCRIPT
REM =================================================================
CLS
ECHO ===========================================
ECHO      TRADETRACKER GIT DATA PUSHER
ECHO ===========================================
ECHO.

ECHO [*] Navigating to repository: %REPO_PATH%
cd /d %REPO_PATH%
IF ERRORLEVEL 1 (
    ECHO [!!!] FATAL ERROR: Could not navigate to the repository path.
    goto:error_exit
)

ECHO [*] Staging all new and modified files...
git add .

ECHO [*] Checking for changes to commit...
git diff-index --quiet HEAD --
IF ERRORLEVEL 1 (
    ECHO [*] Changes detected. Committing with a timestamp...
    
    REM Use PowerShell for a clean, sortable timestamp (YYYY-MM-DD HH:mm:ss)
    FOR /f "tokens=*" %%g IN ('powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"') do (SET "TIMESTAMP=%%g")

    REM Correctly quoted commit command
    git commit -m "%COMMIT_MESSAGE%: %TIMESTAMP%"
    IF ERRORLEVEL 1 (
        ECHO [!!!] FATAL ERROR: 'git commit' failed.
        goto:error_exit
    )
) ELSE (
    ECHO [*] No changes to commit. Nothing to do.
)

ECHO.
ECHO [*] Pulling latest changes from the remote repository...
REM Using --rebase is often better for automated scripts to avoid merge commits
git pull --rebase %REMOTE_NAME% %BRANCH_NAME%
IF ERRORLEVEL 1 (
    ECHO [!!!] FATAL ERROR: 'git pull --rebase' failed. A manual merge is required.
    ECHO [!!!] Open a terminal, 'cd' to the repo, and run 'git status' to fix.
    goto:error_exit
)

ECHO.
ECHO [*] Pushing your local commits to the online repository...
git push %REMOTE_NAME% %BRANCH_NAME%
IF ERRORLEVEL 1 (
    ECHO [!] WARNING: 'git push' failed. This is often normal if the remote was already up-to-date.
)

ECHO.
ECHO ===========================================
ECHO           PROCESS COMPLETE
ECHO ===========================================
ECHO.
pause
exit /b 0

:error_exit
ECHO.
ECHO Script encountered a fatal error and cannot continue.
pause
exit /b 1