@echo off
setlocal

if not exist venv\Scripts\python.exe (
    echo [ERROR] venv not found. Run setup.bat first.
    pause
    exit /b 1
)

echo Starting Ollama...
start "Ollama" /min ollama serve
timeout /t 2 /nobreak >nul

echo Launching LocalAgentOS...
venv\Scripts\python.exe main.py %*
