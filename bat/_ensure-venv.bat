@echo off
rem Helper for run-app.bat / run-test.bat: creates .venv if missing and installs
rem requirements.txt (analogue of the restore step in "dotnet run" / "dotnet test").
rem Expects the current directory to be the repository root.
if not exist ".venv\Scripts\python.exe" (
  echo Создаю .venv ...
  py -3 -m venv .venv 2>nul || python -m venv .venv || exit /b 1
)
echo Проверяю зависимости из requirements.txt ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || exit /b 1
exit /b 0
