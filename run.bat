@echo off
TITLE TradeTracker Data Pusher

REM =================================================================
REM      CONFIGURATION - This is the only part you might change.
REM =================================================================

REM The full path to your project folder.
SET REPO_PATH="C:\Users\River\tradetracker"

REM The name of the remote to push to (usually "origin").
SET REMOTE_NAME="origin"

REM The name of the branch to push (usually "main" or "master").
SET BRANCH_NAME="main"

REM The message for the automatic commit.
SET COMMIT_MESSAGE="Automated data update"


REM =================================================================
REM      GIT AUTOMATION SCRIPT - Do not edit below this line.
REM =================================================================
CLS
ECHO ===========================================
ECHO      TRADETRACKER GIT DATA PUSHER
ECHO ===========================================
ECHO.

ECHO [*] Navigating to repository: %REPO_PATH%
cd /d %REPO_PATH%

ECHO.
ECHO [*] Staging all new and modified files...
git add .

ECHO.
ECHO [*] Committing the changes with a timestamp...
git commit -m "%COMMIT_MESSAGE% - %DATE% %TIME%"

ECHO.
ECHO [*] Pulling latest changes from the remote repository...
git pull %REMOTE_NAME% %BRANCH_NAME%

ECHO.
ECHO [*] Pushing your local commits to the online repository...
git push %REMOTE_NAME% %BRANCH_NAME%

ECHO.
ECHO ===========================================
ECHO           PROCESS COMPLETE
ECHO ===========================================
ECHO.
pause