@echo off
setlocal
cd /d "%~dp0"

:: Проверяем, есть ли папка .venv или venv
if exist .venv\Scripts\activate (
    set VENV_PATH=.venv
) else if exist venv\Scripts\activate (
    set VENV_PATH=venv
) else (
    echo [ERROR] Virtual environment not found! Creating new one...
    python -m venv venv
    set VENV_PATH=venv
)

echo Using venv from: %VENV_PATH%
call %VENV_PATH%\Scripts\activate

:: Устанавливаем зависимости на случай, если их нет
echo Checking dependencies...
python -m pip install -r requirements.txt

:: Запуск сервера
echo Starting server...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

pause