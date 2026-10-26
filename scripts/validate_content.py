#!/usr/bin/env python3
"""Валидатор файлов содержания курса: course.json, slice.json, demo.json,
questions.json, assignments.json.

Схема — в docs/spec/content-schema.md. Скрипт намеренно простой (без jsonschema),
чтобы работать в любой среде без зависимостей. Код выхода 1 = есть нарушения.
Вызов: python3 scripts/validate_content.py <file.json>
"""
import json
import os
import re
import sys

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TRACKS = {"genai", "xai"}
PERIODS = {"golden", "winter"}
STATUSES = {"draft", "approved"}
PAGE_TYPES = {
    "overview",          # обзорная страница общего характера
    "winter-overview",   # обзор winter-периода: на что смещались ожидания и почему
    "idea",              # новая идея — предварительное неформальное описание
    "math",              # математический аппарат идеи
    "library",           # возможности NumPy/PyTorch применительно к текущему примеру
    "code-example",      # пример сети с кодом реализации
    "demo",              # то же + визуализация (проигрывание трассы)
    "history",           # исторический экскурс, биографическая врезка
    "summary",           # резюме среза
    "questions",         # вопросы для самоконтроля (раскрываемые ответы)
    "assignments",       # задания для самостоятельных экспериментов
}

errors = []


def err(msg):
    errors.append(msg)


def require(obj, keys, ctx):
    for k in keys:
        if k not in obj:
            err(f"{ctx}: нет обязательного поля '{k}'")


def check_id(value, ctx):
    if not isinstance(value, str) or not ID_RE.match(value):
        err(f"{ctx}: id '{value}' должен быть kebab-case (a-z, 0-9, -)")


def check_year(value, ctx):
    if not isinstance(value, int) or not (1900 <= value <= 2035):
        err(f"{ctx}: год '{value}' вне диапазона 1900..2035")


def validate_course(d):
    ctx = "course.json"
    require(d, ["title", "slices"], ctx)
    slices = d.get("slices", [])
    if not isinstance(slices, list) or not slices:
        err(f"{ctx}: 'slices' — непустой упорядоченный список срезов")
        return
    seen = set()
    for i, s in enumerate(slices):
        sctx = f"{ctx}: slices[{i}]"
        require(s, ["id", "title"], sctx)
        if "id" in s:
            check_id(s["id"], sctx)
            if s["id"] in seen:
                err(f"{sctx}: дублирующийся id {s['id']}")
            seen.add(s["id"])


def validate_slice(d, path):
    ctx = "slice.json"
    require(d, ["id", "title", "yearFrom", "yearTo", "track", "period",
                "summary", "pages", "status"], ctx)
    if "id" in d:
        check_id(d["id"], ctx)
        folder = os.path.basename(os.path.dirname(os.path.abspath(path)))
        if folder and folder != d["id"]:
            err(f"{ctx}: id '{d['id']}' не совпадает с именем папки '{folder}'")
    for k in ("yearFrom", "yearTo"):
        if k in d:
            check_year(d[k], ctx)
    if {"yearFrom", "yearTo"} <= d.keys() and isinstance(d["yearFrom"], int) \
            and isinstance(d["yearTo"], int) and d["yearFrom"] > d["yearTo"]:
        err(f"{ctx}: yearFrom > yearTo")
    if d.get("track") not in TRACKS:
        err(f"{ctx}: track должен быть одним из {sorted(TRACKS)}")
    if d.get("period") not in PERIODS:
        err(f"{ctx}: period должен быть одним из {sorted(PERIODS)}")
    if d.get("status") not in STATUSES:
        err(f"{ctx}: status должен быть одним из {sorted(STATUSES)}")
    pages = d.get("pages", [])
    if not isinstance(pages, list) or not pages:
        err(f"{ctx}: 'pages' — непустой упорядоченный список страниц")
        return
    seen = set()
    base = os.path.dirname(os.path.abspath(path))
    for i, p in enumerate(pages):
        pctx = f"{ctx}: pages[{i}]"
        require(p, ["id", "type", "file"], pctx)
        if "id" in p:
            check_id(p["id"], pctx)
            if p["id"] in seen:
                err(f"{pctx}: дублирующийся id {p['id']}")
            seen.add(p["id"])
        if p.get("type") not in PAGE_TYPES:
            err(f"{pctx}: type '{p.get('type')}' не входит в типологию "
                f"(docs/spec/content-schema.md): {sorted(PAGE_TYPES)}")
        f = p.get("file")
        if isinstance(f, str) and not os.path.exists(os.path.join(base, f)):
            err(f"{pctx}: файл '{f}' не найден рядом со slice.json")


def validate_demo(d, path):
    ctx = "demo.json"
    require(d, ["id", "title", "entry", "trace", "gen"], ctx)
    if "id" in d:
        check_id(d["id"], ctx)
    base = os.path.dirname(os.path.abspath(path))
    for k in ("entry", "trace"):
        f = d.get(k)
        if isinstance(f, str) and not os.path.exists(os.path.join(base, f)):
            err(f"{ctx}: '{k}' указывает на несуществующий файл '{f}'")
    gen = d.get("gen", {})
    if not isinstance(gen, dict) or not (set(gen) & {"numpy", "torch"}):
        err(f"{ctx}: 'gen' должен указывать хотя бы одну реализацию: numpy и/или torch")
    else:
        for lib, f in gen.items():
            if lib not in ("numpy", "torch"):
                err(f"{ctx}: gen.{lib} — допустимы только 'numpy' и 'torch'")
            elif isinstance(f, str) and not os.path.exists(os.path.join(base, f)):
                err(f"{ctx}: gen.{lib} указывает на несуществующий файл '{f}'")


def validate_questions(d):
    ctx = "questions.json"
    if not isinstance(d, list) or not d:
        err(f"{ctx}: ожидается непустой список вопросов")
        return
    for i, q in enumerate(d):
        qctx = f"{ctx}[{i}]"
        require(q, ["id", "question", "answer"], qctx)
        if "id" in q:
            check_id(q["id"], qctx)


def validate_assignments(d):
    ctx = "assignments.json"
    if not isinstance(d, list) or not d:
        err(f"{ctx}: ожидается непустой список заданий")
        return
    for i, a in enumerate(d):
        actx = f"{ctx}[{i}]"
        require(a, ["id", "task"], actx)
        if "id" in a:
            check_id(a["id"], actx)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        print(f"{path}: не читается как JSON: {e}")
        return 1

    name = os.path.basename(path)
    if name == "course.json":
        validate_course(d)
    elif name == "slice.json":
        validate_slice(d, path)
    elif name == "demo.json":
        validate_demo(d, path)
    elif name == "questions.json":
        validate_questions(d)
    elif name == "assignments.json":
        validate_assignments(d)
    else:
        print(f"{path}: неизвестный тип файла содержания — пропущен")
        return 0

    if errors:
        print(f"{path}: {len(errors)} нарушение(й):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{path}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
