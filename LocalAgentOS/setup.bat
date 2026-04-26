@echo off
setlocal

set PY310=C:\Users\tyler\AppData\Local\Programs\Python\Python310\python.exe

echo.
echo ================================================
echo   LocalAgentOS Setup  (Python 3.10)
echo ================================================
echo.

if not exist "%PY310%" (
    echo [ERROR] Python 3.10 not found at:
    echo         %PY310%
    echo         Re-install Python 3.10 from https://python.org
    pause
    exit /b 1
)
echo [OK] Python 3.10 found.

echo Creating virtual environment (venv)...
"%PY310%" -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)
echo [OK] venv created.

echo Upgrading pip / setuptools / wheel inside venv...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel --quiet
echo [OK] pip upgraded.

echo Installing Pillow (binary wheel)...
venv\Scripts\python.exe -m pip install "Pillow>=10.4.0" --only-binary=:all: --quiet
echo [OK] Pillow installed.

echo Attempting PyAudio install (enables mic input)...
venv\Scripts\python.exe -m pip install PyAudio --only-binary=:all: --quiet
if not errorlevel 1 goto pyaudio_ok
venv\Scripts\python.exe -m pip install pipwin --quiet
venv\Scripts\python.exe -m pipwin install pyaudio --quiet
if not errorlevel 1 goto pyaudio_ok
echo [WARN] PyAudio unavailable - mic input disabled. TTS still works.
goto pyaudio_done
:pyaudio_ok
echo [OK] PyAudio installed - mic input enabled.
:pyaudio_done

echo Installing all packages...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
echo [OK] All packages installed.

ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARN] Ollama not found. Download from: https://ollama.com/download
    echo        Then re-run this script to pull the model.
    goto ollama_done
)
echo [OK] Ollama found.
echo Pulling llama3.1:8b (~4.7 GB first time)...
ollama pull llama3.1:8b
if errorlevel 1 (
    echo [WARN] Model pull failed. Run manually: ollama pull llama3.1:8b
) else (
    echo [OK] llama3.1:8b ready.
)
:ollama_done

if not exist .env (
    (
        echo OLLAMA_HOST=http://localhost:11434
        echo OLLAMA_MODEL=llama3.1:8b
        echo ELEVENLABS_API_KEY=
        echo ELEVENLABS_VOICE=Bella
    ) > .env
    echo [OK] .env created.
)

echo.
echo ================================================
echo   Done!
echo   Launch with:    launch.bat
echo   CLI test mode:  launch.bat --cli
echo ================================================
pause
