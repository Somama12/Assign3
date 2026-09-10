"""Tests for the PawPal+ logic layer."""

from datetime import date, time

import pytest

from pawpal_system import (
    Conflict,
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


def test_remove_task_at_targets_one_of_two_same_titled_tasks(pet: Pet) -> None:
    """Position-based removal distinguishes tasks that share a title."""
    pet.add_task(Task("Walk", duration_minutes=20))
    pet.add_task(Task("Walk", duration_minutes=45))

    assert pet.remove_task_at(0) is True

    assert [t.duration_minutes for t in pet.tasks] == [45]
    assert pet.remove_task_at(5) is False


def test_remove_pet_at_targets_by_position() -> None:
    """Position-based pet removal works even if two pets share a name."""
    owner = Owner("Jordan", pets=[Pet("Mochi", "dog"), Pet("Mochi", "cat")])

    assert owner.remove_pet_at(0) is True

    assert [p.species for p in owner.pets] == ["cat"]
    assert owner.remove_pet_at(3) is False


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


# --- Sorting ----------------------------------------------------------------


def test_sort_by_time_puts_fixed_times_first_in_clock_order() -> None:
    """sort_by_time() orders pinned tasks by clock and leaves the rest at the end."""
    evening = Task("Evening walk", 25, preferred_time=time(18, 0))
    morning = Task("Morning walk", 30, preferred_time=time(8, 0))
    anytime = Task("Puzzle feeder", 15)

    ordered = Scheduler().sort_by_time([evening, anytime, morning])

    assert [t.title for t in ordered] == ["Morning walk", "Evening walk", "Puzzle feeder"]


def test_sort_by_time_is_stable_for_unpinned_tasks() -> None:
    """Tasks without a fixed time keep the order they were entered in."""
    first = Task("Breakfast", 10)
    second = Task("Dinner", 10)

    ordered = Scheduler().sort_by_time([first, second])

    assert [t.title for t in ordered] == ["Breakfast", "Dinner"]


def test_sort_by_priority_orders_high_first_then_shortest() -> None:
    """sort_by_priority() ranks by priority, breaking ties with duration."""
    tasks = [
        Task("Long medium", 40, priority=Priority.MEDIUM),
        Task("Low", 5, priority=Priority.LOW),
        Task("Short medium", 10, priority=Priority.MEDIUM),
        Task("High", 30, priority=Priority.HIGH),
    ]

    ordered = Scheduler().sort_by_priority(tasks)

    assert [t.title for t in ordered] == ["High", "Short medium", "Long medium", "Low"]


# --- Filtering --------------------------------------------------------------


def test_filter_tasks_by_completion_status(pet: Pet) -> None:
    """filter_tasks(completed=...) splits done from pending."""
    walk = Task("Morning walk", 30)
    pet.add_task(walk)
    pet.add_task(Task("Breakfast", 10))
    walk.mark_complete()

    assert [t.title for t in pet.filter_tasks(completed=True)] == ["Morning walk"]
    assert [t.title for t in pet.filter_tasks(completed=False)] == ["Breakfast"]


def test_filter_tasks_by_pet_name() -> None:
    """Owner.filter_tasks(pet_name=...) narrows to one pet."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Walk", 30))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Wet food", 10))
    owner = Owner("Jordan", pets=[mochi, pickle])

    assert [t.title for t in owner.filter_tasks(pet_name="Pickle")] == ["Wet food"]
    assert len(owner.filter_tasks()) == 2
    assert owner.filter_tasks(pet_name="Nobody") == []


def test_filter_tasks_combines_criteria(pet: Pet) -> None:
    """Every supplied criterion has to match, not just one of them."""
    pet.add_task(Task("Meds", 5, priority=Priority.HIGH))
    pet.add_task(Task("Walk", 30, priority=Priority.HIGH, frequency=Frequency.WEEKLY))
    owner = Owner("Jordan", pets=[pet])

    matches = owner.filter_tasks(priority="high", frequency="daily")

    assert [t.title for t in matches] == ["Meds"]


# --- Recurring tasks --------------------------------------------------------


def test_completing_a_daily_task_queues_tomorrow(pet: Pet) -> None:
    """A completed daily task reappears due the next day."""
    walk = Task("Morning walk", 30, priority=Priority.HIGH)
    pet.add_task(walk)

    follow_up = pet.complete_task(walk, today=MONDAY)

    assert walk.completed is True
    assert follow_up.completed is False
    assert follow_up.due_date == date(2026, 9, 15)
    assert len(pet.tasks) == 2


def test_completing_a_weekly_task_queues_next_week(pet: Pet) -> None:
    """A completed weekly task reappears on the same weekday next week."""
    grooming = Task("Brush coat", 20, frequency=Frequency.WEEKLY, weekly_day=0)
    pet.add_task(grooming)

    follow_up = pet.complete_task(grooming, today=MONDAY)

    assert follow_up.due_date == date(2026, 9, 21)
    assert follow_up.due_date.weekday() == 0


def test_weekly_follow_up_lands_on_its_weekday_even_when_completed_late(pet: Pet) -> None:
    """Completing a Monday task on Tuesday still queues the following Monday."""
    grooming = Task("Brush coat", 20, frequency=Frequency.WEEKLY, weekly_day=0)
    pet.add_task(grooming)

    follow_up = pet.complete_task(grooming, today=TUESDAY)

    assert follow_up.due_date == date(2026, 9, 21)
    assert follow_up.due_date.weekday() == 0


def test_follow_up_is_not_due_today(owner: Owner, pet: Pet) -> None:
    """The queued occurrence stays out of today's plan."""
    walk = Task("Morning walk", 30, priority=Priority.HIGH)
    pet.add_task(walk)
    pet.complete_task(walk, today=MONDAY)

    plan = Scheduler().build_plan(owner, pet, day=MONDAY)

    assert plan.is_empty
    assert len(pet.pending_tasks()) == 1


def test_overdue_task_stays_due(pet: Pet) -> None:
    """A task due yesterday is still due today rather than vanishing."""
    task = Task("Meds", 5, due_date=MONDAY)

    assert task.is_due_on(MONDAY) is True
    assert task.is_due_on(TUESDAY) is True
    assert task.is_due_on(date(2026, 9, 13)) is False


def test_undoing_a_completion_removes_the_queued_follow_up(pet: Pet) -> None:
    """Undo leaves no phantom duplicate behind."""
    walk = Task("Morning walk", 30)
    pet.add_task(walk)
    pet.complete_task(walk, today=MONDAY)
    assert len(pet.tasks) == 2

    removed = pet.uncomplete_task(walk, today=MONDAY)

    assert removed is True
    assert walk.completed is False
    assert pet.tasks == [walk]


def test_undo_without_a_follow_up_still_reopens_the_task(pet: Pet) -> None:
    """Undoing a plain completion works even with no follow-up to remove."""
    walk = Task("Morning walk", 30)
    pet.add_task(walk)
    walk.mark_complete()

    assert pet.uncomplete_task(walk, today=MONDAY) is False
    assert walk.completed is False


def test_complete_task_rejects_a_task_from_another_pet(pet: Pet) -> None:
    """complete_task() only accepts tasks it actually owns."""
    stranger = Task("Someone else's walk", 30)

    assert pet.complete_task(stranger, today=MONDAY) is None
    assert stranger.completed is False


# --- Conflict detection -----------------------------------------------------


def test_conflict_detected_between_two_pets() -> None:
    """Two pets pinned to the same time is a conflict the owner should see."""
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, preferred_time=time(8, 0)))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Insulin", 10, preferred_time=time(8, 15)))
    owner = Owner("Jordan", pets=[mochi, pickle])

    conflicts = Scheduler().find_conflicts(owner, day=MONDAY)

    assert len(conflicts) == 1
    assert isinstance(conflicts[0], Conflict)
    assert "two places at once" in conflicts[0].message


def test_conflict_detected_within_one_pet() -> None:
    """Two overlapping fixed times for the same pet also conflict."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, preferred_time=time(8, 0)))
    pet.add_task(Task("Bath", 20, preferred_time=time(8, 20)))
    owner = Owner("Jordan", pets=[pet])

    conflicts = Scheduler().find_conflicts(owner, day=MONDAY)

    assert len(conflicts) == 1
    assert conflicts[0].message.startswith("Mochi:")


def test_back_to_back_tasks_do_not_conflict() -> None:
    """A task starting exactly when another ends is fine."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, preferred_time=time(8, 0)))
    pet.add_task(Task("Breakfast", 10, preferred_time=time(8, 30)))
    owner = Owner("Jordan", pets=[pet])

    assert Scheduler().find_conflicts(owner, day=MONDAY) == []


def test_conflict_sweep_reports_every_overlapping_pair() -> None:
    """One long task overlapping two later ones yields all three pairs.

    A naive "compare each task to the next one after sorting" would miss the
    long-vs-last pair, so this pins the sweep down.
    """
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Long groom", 60, preferred_time=time(8, 0)))
    pet.add_task(Task("Meds", 5, preferred_time=time(8, 10)))
    pet.add_task(Task("Drops", 5, preferred_time=time(8, 50)))
    owner = Owner("Jordan", pets=[pet])

    conflicts = Scheduler().find_conflicts(owner, day=MONDAY)
    pairs = {(c.first.title, c.second.title) for c in conflicts}

    assert pairs == {
        ("Long groom", "Meds"),
        ("Long groom", "Drops"),
    }


def test_unpinned_tasks_never_conflict() -> None:
    """Tasks without a fixed time are free to move, so they cannot clash."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30))
    pet.add_task(Task("Breakfast", 10))
    owner = Owner("Jordan", pets=[pet])

    assert Scheduler().find_conflicts(owner, day=MONDAY) == []


def test_completed_task_is_not_a_conflict() -> None:
    """A task already done cannot clash with anything."""
    pet = Pet("Mochi", "dog")
    done = Task("Walk", 30, preferred_time=time(8, 0))
    pet.add_task(done)
    pet.add_task(Task("Insulin", 10, preferred_time=time(8, 15)))
    done.mark_complete()
    owner = Owner("Jordan", pets=[pet])

    assert Scheduler().find_conflicts(owner, day=MONDAY) == []


def test_conflict_warnings_returns_strings_and_never_raises() -> None:
    """conflict_warnings() hands back printable messages, not exceptions."""
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 30, preferred_time=time(8, 0)))
    pet.add_task(Task("Bath", 20, preferred_time=time(8, 10)))
    owner = Owner("Jordan", pets=[pet])

    warnings = Scheduler().conflict_warnings(owner, day=MONDAY)

    assert len(warnings) == 1
    assert all(isinstance(w, str) for w in warnings)
    assert Scheduler().conflict_warnings(Owner("Nobody"), day=MONDAY) == []
