"""Tests for the PawPal+ logic layer."""

from datetime import date, time

import pytest

from pawpal_system import (
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

MONDAY = date(2026, 9, 14)
TUESDAY = date(2026, 9, 15)


@pytest.fixture
def pet() -> Pet:
    """A pet with no tasks yet."""
    return Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3)


@pytest.fixture
def owner(pet: Pet) -> Owner:
    """An owner with 90 minutes free and one pet."""
    owner = Owner(name="Jordan", minutes_available=90)
    owner.add_pet(pet)
    return owner


# --- Required Phase 2 tests -------------------------------------------------


def test_mark_complete_changes_status() -> None:
    """mark_complete() flips a task from pending to done."""
    task = Task("Morning walk", duration_minutes=30)
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count(pet: Pet) -> None:
    """Adding a task to a pet grows that pet's task list."""
    assert len(pet.tasks) == 0

    pet.add_task(Task("Breakfast", duration_minutes=10))
    assert len(pet.tasks) == 1

    pet.add_task(Task("Evening walk", duration_minutes=25))
    assert len(pet.tasks) == 2


# --- Data model -------------------------------------------------------------


def test_pending_tasks_excludes_completed(pet: Pet) -> None:
    """A completed task drops out of pending_tasks()."""
    walk = Task("Morning walk", duration_minutes=30)
    pet.add_task(walk)
    pet.add_task(Task("Breakfast", duration_minutes=10))

    walk.mark_complete()

    assert [t.title for t in pet.pending_tasks()] == ["Breakfast"]
    assert [t.title for t in pet.completed_tasks()] == ["Morning walk"]


def test_remove_task_reports_whether_it_removed_anything(pet: Pet) -> None:
    """remove_task() returns True only when a matching task existed."""
    pet.add_task(Task("Breakfast", duration_minutes=10))

    assert pet.remove_task("Breakfast") is True
    assert pet.remove_task("Breakfast") is False
    assert pet.tasks == []


def test_zero_duration_task_is_rejected() -> None:
    """A task has to take some time, or scheduling it is meaningless."""
    with pytest.raises(ValueError, match="must be positive"):
        Task("Ghost task", duration_minutes=0)


def test_priority_accepts_ui_strings() -> None:
    """Strings from the Streamlit selectbox parse into the Priority enum."""
    assert Task("Meds", 5, priority="high").priority is Priority.HIGH
    assert Priority.HIGH > Priority.LOW

    with pytest.raises(ValueError, match="unknown priority"):
        Task("Meds", 5, priority="urgent")


def test_owner_all_tasks_spans_every_pet() -> None:
    """The owner exposes tasks across all their pets, which is what the scheduler reads."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Walk", 30))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Wet food", 10))
    owner = Owner("Jordan", pets=[mochi, pickle])

    assert len(owner.all_tasks()) == 2
    assert owner.tasks_by_pet().keys() == {"Mochi", "Pickle"}


# --- Frequency --------------------------------------------------------------


def test_weekly_task_is_only_due_on_its_day() -> None:
    """A weekly task is due on its weekday and skipped on the others."""
    grooming = Task(
        "Brush coat",
        duration_minutes=20,
        frequency=Frequency.WEEKLY,
        weekly_day=0,
    )

    assert grooming.is_due_on(MONDAY) is True
    assert grooming.is_due_on(TUESDAY) is False


def test_daily_task_is_due_every_day() -> None:
    """A daily task is due regardless of weekday."""
    walk = Task("Morning walk", duration_minutes=30)

    assert walk.is_due_on(MONDAY) is True
    assert walk.is_due_on(TUESDAY) is True


# --- Scheduling -------------------------------------------------------------


def test_plan_orders_by_priority(owner: Owner, pet: Pet) -> None:
    """Higher priority tasks get the earlier slots."""
    pet.add_task(Task("Enrichment", 15, priority=Priority.LOW))
    pet.add_task(Task("Meds", 15, priority=Priority.HIGH))
    pet.add_task(Task("Grooming", 15, priority=Priority.MEDIUM))

    plan = Scheduler().build_plan(owner, pet, day=MONDAY)

    assert [item.task.title for item in plan.scheduled] == [
        "Meds",
        "Grooming",
        "Enrichment",
    ]


def test_plan_respects_the_time_budget(owner: Owner, pet: Pet) -> None:
    """Tasks past the owner's available minutes are skipped, not squeezed in."""
    owner.minutes_available = 40
    pet.add_task(Task("Morning walk", 30, priority=Priority.HIGH))
    pet.add_task(Task("Breakfast", 10, priority=Priority.HIGH))
    pet.add_task(Task("Clip nails", 25, priority=Priority.LOW))

    plan = Scheduler().build_plan(owner, pet, day=MONDAY)

    assert plan.minutes_used == 40
    assert plan.minutes_remaining == 0
    assert [item.task.title for item in plan.skipped] == ["Clip nails"]
    assert "only 0 min left" not in plan.skipped[0].reason


def test_anchored_task_keeps_its_preferred_time(owner: Owner, pet: Pet) -> None:
    """A task with a preferred_time is placed at exactly that time."""
    pet.add_task(Task("Thyroid meds", 5, priority=Priority.HIGH, preferred_time=time(9, 0)))
    pet.add_task(Task("Breakfast", 10, priority=Priority.HIGH))

    plan = Scheduler(day_start=time(8, 0)).build_plan(owner, pet, day=MONDAY)
    placed = {item.task.title: item.start_time for item in plan.scheduled}

    assert placed["Thyroid meds"] == time(9, 0)
    assert placed["Breakfast"] == time(8, 0)


def test_flexible_task_fills_the_gap_before_an_anchor(owner: Owner, pet: Pet) -> None:
    """A short task slots into the gap ahead of a fixed-time task."""
    pet.add_task(Task("Thyroid meds", 5, priority=Priority.HIGH, preferred_time=time(8, 30)))
    pet.add_task(Task("Breakfast", 10, priority=Priority.MEDIUM))

    plan = Scheduler(day_start=time(8, 0)).build_plan(owner, pet, day=MONDAY)

    assert [(i.task.title, i.start_time) for i in plan.scheduled] == [
        ("Breakfast", time(8, 0)),
        ("Thyroid meds", time(8, 30)),
    ]


def test_anchored_task_outside_the_day_is_skipped(owner: Owner, pet: Pet) -> None:
    """A preferred time past the end of the day cannot be honored."""
    pet.add_task(Task("Midnight snack", 10, preferred_time=time(23, 30)))

    plan = Scheduler(day_start=time(8, 0), day_end=time(21, 0)).build_plan(
        owner, pet, day=MONDAY
    )

    assert plan.is_empty
    assert "outside the" in plan.skipped[0].reason


def test_weekly_task_absent_from_a_plan_on_the_wrong_day(owner: Owner, pet: Pet) -> None:
    """A weekly task neither runs nor shows as skipped on a day it isn't due."""
    pet.add_task(Task("Brush coat", 20, frequency=Frequency.WEEKLY, weekly_day=0))

    tuesday_plan = Scheduler().build_plan(owner, pet, day=TUESDAY)

    assert tuesday_plan.is_empty
    assert tuesday_plan.skipped == []


def test_completed_task_is_not_rescheduled(owner: Owner, pet: Pet) -> None:
    """Once a task is done it drops out of the day's plan."""
    walk = Task("Morning walk", 30, priority=Priority.HIGH)
    pet.add_task(walk)
    walk.mark_complete()

    plan = Scheduler().build_plan(owner, pet, day=MONDAY)

    assert plan.is_empty


def test_owner_preferences_break_a_priority_tie(pet: Pet) -> None:
    """Among equal-priority tasks, the one matching a preference goes first."""
    owner = Owner("Jordan", minutes_available=90, preferences=["walk"], pets=[pet])
    pet.add_task(Task("Nap supervision", 15, priority=Priority.MEDIUM))
    pet.add_task(Task("Evening walk", 15, priority=Priority.MEDIUM))

    plan = Scheduler().build_plan(owner, pet, day=MONDAY)

    assert plan.scheduled[0].task.title == "Evening walk"
    assert "matches your preferences" in plan.scheduled[0].reason


# --- Multi-pet scheduling ---------------------------------------------------


def test_high_priority_task_beats_another_pets_low_priority_task() -> None:
    """Priority is compared across all pets, not pet by pet."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Breakfast", 30, priority=Priority.HIGH))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Clip nails", 30, priority=Priority.LOW))
    owner = Owner("Jordan", minutes_available=30, pets=[mochi, pickle])

    mochi_plan, pickle_plan = Scheduler().build_plans(owner, day=MONDAY)

    assert [i.task.title for i in mochi_plan.scheduled] == ["Breakfast"]
    assert pickle_plan.is_empty
    assert [i.task.title for i in pickle_plan.skipped] == ["Clip nails"]


def test_two_pets_tasks_never_overlap_on_the_clock() -> None:
    """The owner has one pair of hands, so no two tasks share wall-clock time."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, priority=Priority.HIGH))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Wet food", 10, priority=Priority.HIGH))
    owner = Owner("Jordan", minutes_available=90, pets=[mochi, pickle])

    plans = Scheduler(day_start=time(8, 0)).build_plans(owner, day=MONDAY)
    windows = sorted(
        (item.start_time, item.end_time())
        for plan in plans
        for item in plan.scheduled
    )

    assert len(windows) == 2
    for (_, earlier_end), (later_start, _) in zip(windows, windows[1:]):
        assert earlier_end <= later_start


def test_shared_budget_is_not_spent_twice() -> None:
    """Both pets draw from the same pool of minutes."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, priority=Priority.HIGH))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Wand play", 30, priority=Priority.MEDIUM))
    owner = Owner("Jordan", minutes_available=45, pets=[mochi, pickle])

    plans = Scheduler().build_plans(owner, day=MONDAY)
    total_used = sum(plan.minutes_used for plan in plans)

    assert total_used == 30
    assert total_used <= owner.minutes_available


def test_explain_mentions_scheduled_and_skipped(owner: Owner, pet: Pet) -> None:
    """The explanation covers what was planned and what was left out."""
    owner.minutes_available = 30
    pet.add_task(Task("Morning walk", 30, priority=Priority.HIGH))
    pet.add_task(Task("Clip nails", 25, priority=Priority.LOW))
    scheduler = Scheduler()

    text = scheduler.explain(scheduler.build_plan(owner, pet, day=MONDAY))

    assert "Morning walk" in text
    assert "Clip nails" in text
    assert "Left out" in text
