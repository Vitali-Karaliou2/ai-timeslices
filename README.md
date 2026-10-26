# TimeSlices-AI — История ИИ в тематических срезах

Обучающее приложение: история нейронных сетей и генеративного ИИ как линейная
последовательность тематических срезов, с демо-визуализациями обучения сетей
(NumPy/PyTorch) и самоконтролем в конце каждого среза. См. `docs/brief/` и `CLAUDE.md`.

Стадия 0→1. Окружение: `bash scripts/setup_env.sh`; тесты: `pytest`;
запуск: `uvicorn app.main:app --reload --port 8000`.

Windows: `bat\run-app.bat` — запуск на http://localhost:8000 (открывает браузер),
`bat\run-test.bat` — все тесты. При первом запуске создают `.venv` и ставят
`requirements.txt` (нужен Python 3.11+ в PATH).
