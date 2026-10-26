@echo off
rem Run all TimeSlices-AI tests (pytest). Needs Python 3.11+ in PATH on first run.
chcp 65001 >nul
cd /d "%~dp0.."
call :ensure_venv || goto :fail
echo Прогон всех тестов TimeSlices-AI...
".venv\Scripts\python.exe" -m pytest
if errorlevel 1 (echo. & echo ЕСТЬ УПАВШИЕ ТЕСТЫ - см. вывод выше.) else (echo. & echo Все тесты прошли.)
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
