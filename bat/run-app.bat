@echo off
rem Run TimeSlices-AI at http://localhost:8000 (Development). Stop: Ctrl+C.
rem First run creates .venv and installs requirements.txt (needs Python 3.11+ in PATH).
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0_ensure-venv.bat" || goto :fail
echo Запуск TimeSlices-AI: http://localhost:8000  (остановить - Ctrl+C)
rem Open the browser a few seconds later, when the server is up.
start "" /min cmd /c "timeout /t 6 /nobreak >nul & start "" http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
pause
exit /b

:fail
echo.
echo Не удалось подготовить окружение Python - см. вывод выше.
pause
exit /b 1
