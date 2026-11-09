@echo off
echo === AEGIS Windows Setup ===
echo.

REM Check Python 3.11
python --version | findstr "3.11" >nul
if errorlevel 1 (
  echo Installing Python 3.11...
  winget install Python.Python.3.11 -e --silent
)

REM Node.js
winget list nodejs | findstr "Node.js" >nul
if errorlevel 1 (
  echo Installing Node.js...
  winget install OpenJS.NodeJS -e --silent
)

REM Docker Desktop (manual if needed)
winget list "Docker Desktop" | findstr "Docker" >nul
if errorlevel 1 (
  echo Please install Docker Desktop manually from docker.com
  pause
)

REM Redis (scoop or download)
winget list Redis | findstr Redis >nul
if errorlevel 1 (
  echo Installing Redis...
  winget install Redis.Redis -e --silent
  net start redis
)

REM Ollama
if not exist ollama.exe (
  echo Downloading Ollama...
  powershell -Command "Invoke-WebRequest -Uri https://ollama.ai/download/ollama-windows-amd64.exe -OutFile ollama.exe"
  ollama.exe serve &
  timeout /t 5
  ollama.exe pull mistral
)

REM Venv and deps
python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

REM Verify
python -c "import torch, sklearn, redis, faiss; print('OK - All deps installed')" || (echo FAIL && exit /b 1)

echo.
echo === Setup COMPLETE! ===
echo Run: call venv\Scripts\activate.bat
echo Then: python scripts/train_models.py
echo Then: python scripts/run_demo.py --no-llm
pause
