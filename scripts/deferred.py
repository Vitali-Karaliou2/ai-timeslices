#!/usr/bin/env python3
"""Реестр решений, отложенных на будущее (docs/deferred/deferred.json), и напоминания о них.

Решение откладывается, когда автор отвечает «решим позже» на вопрос из раздела
«Решения, откладываемые на будущее» очередной логической страницы. Напоминание должно
сработать, когда работа дойдёт до темы, к которой решение относится.

Команды:
  list [--all]          открытые (или все) решения
  check --text "..."    какие открытые решения относятся к тексту (тема страницы, план сессии)
  check --slice <id>    какие открытые решения привязаны к срезу
  validate              проверить формат реестра (код 1 при ошибках)
  hook-prompt           хук UserPromptSubmit: JSON на stdin, напоминание — в контекст Claude
  hook-session          хук SessionStart: краткий список открытых решений — в контекст Claude

Только стандартная библиотека: хуки должны работать и без .venv.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent)
REGISTRY = ROOT / "docs" / "deferred" / "deferred.json"

REQUIRED = ("id", "title", "raised_in", "raised_on", "question", "context", "trigger", "status")
STATUSES = ("open", "resolved")


def load(path=REGISTRY):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate(data):
    """Список нарушений формата; пустой — всё в порядке."""
    errors = []
    items = data.get("items")
    if not isinstance(items, list):
        return ["нет списка items"]
    seen = set()
    for n, it in enumerate(items):
        where = it.get("id") or f"items[{n}]"
        for key in REQUIRED:
            if key not in it:
                errors.append(f"{where}: нет поля {key}")
        if not re.fullmatch(r"D\d{3}", str(it.get("id", ""))):
            errors.append(f"{where}: id должен иметь вид D001")
        if it.get("id") in seen:
            errors.append(f"{where}: дублирующийся id")
        seen.add(it.get("id"))
        if it.get("status") not in STATUSES:
            errors.append(f"{where}: status должен быть open или resolved")
        if it.get("status") == "resolved" and not it.get("resolution"):
            errors.append(f"{where}: у решённого нет resolution")
        trig = it.get("trigger") or {}
        if not (trig.get("keywords") or trig.get("slices")):
            errors.append(f"{where}: trigger без keywords и slices — напоминание никогда не сработает")
    return errors


def _keyword_hit(keyword, text):
    """Латинские слова — целиком (GAN не находится в «organ»); короткие аббревиатуры
    заглавными (RNN, SOM) — с учётом регистра; кириллица — по основе слова."""
    if re.fullmatch(r"[A-Za-z0-9 .·\-]+", keyword):
        flags = 0 if (keyword.isupper() and len(keyword) <= 5) else re.I
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", text, flags) is not None
    return keyword.lower() in text.lower()


def due(data, text="", slice_id=""):
    """Открытые решения, чьи ключевые слова встречаются в тексте или чей срез совпадает."""
    hits = []
    for it in data.get("items", []):
        if it.get("status") != "open":
            continue
        trig = it.get("trigger") or {}
        words = [k for k in trig.get("keywords", []) if text and _keyword_hit(k, text)]
        by_slice = bool(slice_id) and slice_id in trig.get("slices", [])
        by_text_slice = [s for s in trig.get("slices", []) if text and s in text]
        if words or by_slice or by_text_slice:
            hits.append((it, words + by_text_slice + ([slice_id] if by_slice else [])))
    return hits


def format_hits(hits):
    lines = ["НАПОМИНАНИЕ (docs/deferred/deferred.json): к этой теме относятся решения, отложенные автором на будущее."
             " Прежде чем писать текст или код по теме, напомни автору о них, предложи варианты и спроси решение;"
             " после ответа обнови реестр по скиллу deferred-decisions."]
    for it, why in hits:
        lines.append(f"- {it['id']} «{it['title']}» (отложено в {it['raised_in']}; совпало: {', '.join(why)})")
        lines.append(f"  Вопрос: {it['question']}")
    return "\n".join(lines)


def _emit_context(event, text):
    # ensure_ascii=True: вывод не зависит от кодировки консоли (cp1251/cp866 на Windows).
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}},
                     ensure_ascii=True))


def _read_stdin_json():
    # Claude Code передаёт JSON в UTF-8; читаем байты, не полагаясь на кодировку ОС.
    raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
    return json.loads(raw.decode("utf-8") or "{}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list"); pl.add_argument("--all", action="store_true")
    pc = sub.add_parser("check"); pc.add_argument("--text", default=""); pc.add_argument("--slice", default="")
    sub.add_parser("validate")
    sub.add_parser("hook-prompt")
    sub.add_parser("hook-session")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # CLI-вывод по-русски и на Windows
    except (AttributeError, ValueError):
        pass

    # Хуки никогда не должны мешать работе: при любой ошибке — молча выйти с кодом 0.
    if args.cmd in ("hook-prompt", "hook-session"):
        try:
            data = load()
            if args.cmd == "hook-prompt":
                prompt = (_read_stdin_json() or {}).get("prompt", "")
                hits = due(data, text=prompt)
                if hits:
                    _emit_context("UserPromptSubmit", format_hits(hits))
            else:
                open_items = [it for it in data.get("items", []) if it.get("status") == "open"]
                if open_items:
                    titles = "; ".join(f"{it['id']} {it['title']}" for it in open_items)
                    _emit_context("SessionStart",
                                  f"Открытые решения, отложенные на будущее (docs/deferred/deferred.json), — {len(open_items)}: {titles}. "
                                  "Если тема сессии касается одного из них — напомни автору до начала работы.")
        except Exception as e:  # причину видно в stderr, работа не прерывается
            print(f"deferred.py {args.cmd}: {e!r}", file=sys.stderr)
        return 0

    data = load()
    if args.cmd == "validate":
        errors = validate(data)
        for e in errors:
            print(e)
        print("OK" if not errors else f"ошибок: {len(errors)}")
        return 1 if errors else 0
    if args.cmd == "list":
        for it in data.get("items", []):
            if args.all or it.get("status") == "open":
                print(f"{it['id']} [{it['status']}] {it['title']} (отложено в {it['raised_in']})")
        return 0
    if args.cmd == "check":
        hits = due(data, text=args.text, slice_id=args.slice)
        print(format_hits(hits) if hits else "Открытых отложенных решений по этой теме нет.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
