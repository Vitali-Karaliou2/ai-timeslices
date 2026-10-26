@echo off
rem Run TimeSlices-AI at http://localhost:8000 (Development). Stop: Ctrl+C.
rem First run creates .venv and installs requirements.txt (needs Python 3.11+ in PATH).
chcp 65001 >nul
cd /d "%~dp0.."
call :ensure_venv || goto :fail
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

:ensure_venv
rem Creates .venv if missing and installs requirements.txt
rem (analogue of the restore step in "dotnet run" / "dotnet test").
if not exist ".venv\Scripts\python.exe" (
  echo Создаю .venv ...
  py -3 -m venv .venv 2>nul || python -m venv .venv || exit /b 1
)
echo Проверяю зависимости из requirements.txt ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || exit /b 1
exit /b 0
