@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo TalkAgent local model setup
echo.

where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama is not installed or is not in PATH.
    echo.
    echo Please install Ollama for Windows first:
    echo https://ollama.com/download/windows
    echo.
    echo After installation, run this script again.
    pause
    exit /b 1
)

echo Starting Ollama service if it is not already running...
start "Ollama" /min ollama serve
timeout /t 5 /nobreak >nul

echo Checking Ollama connection...
ollama list >nul 2>nul
if errorlevel 1 (
    echo Ollama is installed, but the service is not responding.
    echo Try opening the Ollama app from the Start menu, then run this script again.
    pause
    exit /b 1
)

echo Pulling qwen3:1.7b. This may take a while on first run.
ollama pull qwen3:1.7b
if errorlevel 1 (
    echo Failed to pull qwen3:1.7b.
    pause
    exit /b 1
)

echo Creating local TalkAgent model alias: codex-app
ollama create codex-app -f "%~dp0codex-app.Modelfile"
if errorlevel 1 (
    echo Failed to create codex-app model alias.
    pause
    exit /b 1
)

echo Pulling vision model for image understanding: moondream
ollama pull moondream
if errorlevel 1 (
    echo Failed to pull moondream. Text Q&A can still work, but image understanding may be unavailable.
)

echo.
echo Local model is ready.
ollama list
echo.
echo You can now start TalkAgent with start_desktop_app.vbs or start_desktop_app.bat.
pause
