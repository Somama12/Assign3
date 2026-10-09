"""Compare minimal and constraint-focused briefs using reproducible examples.

Run from the repository root: python -m experiments.compare_slot_strategies
Both candidates were developed/evaluated by Codex in the same session.
"""
from datetime import date, datetime, time, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task

DAY = date(2026, 9, 14)


def minimal_slot(owner, duration_minutes):
    """Brief A: Find the first gap between fixed tasks for all pets."""
    cursor = datetime.combine(DAY, time(8))
    duration = timedelta(minutes=duration_minutes)
    tasks = sorted(
        (t for t in owner.all_tasks() if t.is_anchored and not t.completed and t.is_due_on(DAY)),
        key=lambda t: t.preferred_time,
    )
    for task in tasks:
        start, end = task.window_on(DAY)
        if cursor + duration <= start:
            return cursor.time()
        cursor = max(cursor, end)
    return cursor.time() if cursor + duration <= datetime.combine(DAY, time(21)) else None


def main():
    """Print observed outcomes against explicitly stated expectations."""
    cases = [
        ("Fixed task", Owner("Sam", 60, pets=[Pet("Dog", "dog", tasks=[Task("Walk", 30, preferred_time=time(8))])]), time(8, 30)),
        ("Budget exhausted", Owner("Sam", 30, pets=[Pet("Dog", "dog", tasks=[Task("Walk", 30, preferred_time=time(8))])]), None),
        ("Flexible task", Owner("Sam", 60, pets=[Pet("Cat", "cat", tasks=[Task("Play", 30)])]), time(8, 30)),
    ]
    print("Case              | Minimal | Constrained | Expected")
    for label, owner, expected in cases:
        a = minimal_slot(owner, 10)
        b = Scheduler().next_available_slot(owner, 10, DAY)
        def display(value):
            return value.strftime("%H:%M") if value is not None else "none"
        print(f"{label:17} | {display(a):7} | {display(b):11} | {display(expected)}")
        assert b == expected


if __name__ == "__main__":
    main()
