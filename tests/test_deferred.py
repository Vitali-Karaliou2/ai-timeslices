"""Реестр решений, отложенных на будущее, и хуки-напоминания (scripts/deferred.py)."""
import importlib.util
import io
import json
import sys

from app.config import ROOT_DIR

_spec = importlib.util.spec_from_file_location("deferred", ROOT_DIR / "scripts" / "deferred.py")
deferred = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deferred)


def _item(**kw):
    base = {"id": "D001", "title": "Объём RNN", "raised_in": "11.v1-to-2.prompt", "raised_on": "2026-10-27",
            "question": "?", "context": "", "trigger": {"keywords": ["рекуррент", "GAN"], "slices": ["rnn-1986"]},
            "status": "open", "resolution": "", "resolved_in": ""}
    base.update(kw)
    return base


def test_registry_in_repo_is_valid():
    assert deferred.validate(deferred.load()) == []


def test_validate_catches_errors():
    data = {"items": [_item(), _item(status="resolved"), _item(id="X1", trigger={"keywords": [], "slices": []})]}
    errors = "\n".join(deferred.validate(data))
    assert "дублирующийся id" in errors
    assert "нет resolution" in errors
    assert "id должен иметь вид" in errors
    assert "никогда не сработает" in errors


def test_due_by_cyrillic_stem_and_latin_word():
    data = {"items": [_item()]}
    assert deferred.due(data, text="Срез о рекуррентных сетях")
    assert deferred.due(data, text="Переходим к GAN.")
    # латинское ключевое слово — только целым словом
    assert not deferred.due(data, text="organic, Ganges")


def test_due_by_slice_and_skips_resolved():
    data = {"items": [_item(), _item(id="D002", status="resolved", resolution="решено")]}
    hits = deferred.due(data, slice_id="rnn-1986")
    assert [it["id"] for it, _ in hits] == ["D001"]


def test_hook_prompt_injects_context(monkeypatch, capsys):
    monkeypatch.setattr(deferred, "load", lambda: {"items": [_item()]})
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"prompt": "начнём срез про рекуррентные сети"})))
    assert deferred.main(["hook-prompt"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "D001" in out["hookSpecificOutput"]["additionalContext"]


def test_hooks_are_silent_without_match_or_on_error(monkeypatch, capsys):
    monkeypatch.setattr(deferred, "load", lambda: {"items": [_item()]})
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"prompt": "перцептрон"})))
    assert deferred.main(["hook-prompt"]) == 0
    monkeypatch.setattr(sys, "stdin", io.StringIO("не JSON"))
    assert deferred.main(["hook-prompt"]) == 0
    assert capsys.readouterr().out == ""


def test_hooks_registered_in_settings():
    settings = json.loads((ROOT_DIR / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = json.dumps(settings["hooks"], ensure_ascii=False)
    assert "deferred.py hook-prompt" in commands
    assert "deferred.py hook-session" in commands


def test_hook_prompt_subprocess_cyrillic_with_non_utf8_console():
    """Как вызывает Claude Code: UTF-8 на stdin; кодировка консоли (Windows) не должна мешать."""
    import os
    import subprocess

    env = dict(os.environ, PYTHONIOENCODING="cp1251", CLAUDE_PROJECT_DIR=str(ROOT_DIR))
    prompt = json.dumps({"prompt": "Начнём срез о рекуррентных сетях → LSTM"}, ensure_ascii=False)
    r = subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "deferred.py"), "hook-prompt"],
                       input=prompt.encode("utf-8"), capture_output=True, env=env)
    assert r.returncode == 0
    out = json.loads(r.stdout.decode("ascii"))
    assert "D001" in out["hookSpecificOutput"]["additionalContext"]
