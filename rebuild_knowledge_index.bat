@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Rebuilding TalkAgent knowledge index...
python rebuild_knowledge_index.py
echo.
echo Done. Restart TalkAgent desktop app if it is already open.
pause
