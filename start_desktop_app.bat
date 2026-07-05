@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Starting TalkAgent desktop app...
python -m app.desktop

echo.
echo TalkAgent desktop app closed.
pause
