"""Состояния срезов для пользователя при линейном порядке курса.

Правила (docs/spec/shell-spec.md): первый срез Available; срез недоступен, пока
предыдущий не Done; открытие Available-среза → InProgress; «Срез пройден» → Done;
повторное открытие пройденного среза состояний не меняет.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content import Course
from app.models import SliceState, UserSliceState


def _stored(db: Session, user_id: int) -> dict[str, UserSliceState]:
    rows = db.scalars(select(UserSliceState).where(UserSliceState.user_id == user_id))
    return {r.slice_id: r for r in rows}


def sync_states(db: Session, course: Course, user_id: int) -> dict[str, UserSliceState]:
    """Вычисляет состояния по порядку курса и записывает их в user_slice_state.

    Сохранённые InProgress/Done не понижаются (повторное прохождение их не ломает);
    Unavailable/Available пересчитываются из состояния предыдущего среза.
    Если после перестановки срезов в course.json InProgress/Done-срез оказался после
    непройденного, в БД его состояние сохраняется, а показывается он как Unavailable
    (effective_state); когда предшественники будут пройдены, оно снова станет видно.
    Коммит — только при изменениях.
    """
    stored = _stored(db, user_id)
    changed = False
    prev_done = True  # у первого среза «предыдущий» считается пройденным
    for s in course.slices:
        row = stored.get(s.id)
        if row is None:
            row = UserSliceState(user_id=user_id, slice_id=s.id, last_page=1,
                                 state=SliceState.Unavailable)
            db.add(row)
            stored[s.id] = row
            changed = True
        if row.state not in (SliceState.InProgress, SliceState.Done):
            wanted = SliceState.Available if prev_done else SliceState.Unavailable
            if row.state != wanted:
                row.state = wanted
                changed = True
        prev_done = prev_done and row.state == SliceState.Done
    if changed:
        db.commit()
    return stored


def effective_state(course: Course, states: dict[str, UserSliceState], slice_id: str) -> SliceState:
    """Состояние для показа: срез с непройденным предшественником всегда Unavailable,
    даже если в БД записано InProgress/Done (например, после перестановки срезов)."""
    i = course.index_of(slice_id)
    assert i is not None
    for prev in course.slices[:i]:
        if states[prev.id].state != SliceState.Done:
            return SliceState.Unavailable
    return states[slice_id].state


def open_page(db: Session, row: UserSliceState, n: int) -> None:
    if row.state == SliceState.Available:
        row.state = SliceState.InProgress
    if row.last_page != n:
        row.last_page = n
    if db.dirty:
        db.commit()


def mark_done(db: Session, course: Course, user_id: int, row: UserSliceState) -> bool:
    """InProgress/Done → Done. Неоткрытый (Available) срез пройти нельзя: False."""
    if row.state not in (SliceState.InProgress, SliceState.Done):
        return False
    if row.state == SliceState.Done:
        return True
    row.state = SliceState.Done
    db.commit()
    sync_states(db, course, user_id)  # следующий срез становится Available
    return True
