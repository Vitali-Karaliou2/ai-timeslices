@echo off
rem Run all TimeSlices-AI tests (pytest). Needs Python 3.11+ in PATH on first run.
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0_ensure-venv.bat" || goto :fail
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
