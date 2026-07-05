@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Starting TalkAgent UI...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3.14 run_talkagent_ui.py
) else (
    python run_talkagent_ui.py
)

echo.
echo TalkAgent stopped or failed to start.
echo If there is an error above, keep this window open and send the message to Codex.
pause
