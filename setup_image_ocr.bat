@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Installing local image OCR dependency into .deps ...
python -m pip install --target .deps rapidocr-onnxruntime
if errorlevel 1 (
    echo.
    echo Failed to install rapidocr-onnxruntime.
    echo Please check your network or proxy, then run this script again.
    pause
    exit /b 1
)

echo.
echo Image OCR dependency is ready.
echo Restart TalkAgent desktop app and re-upload documents that contain images.
pause
