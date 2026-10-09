"""CLI demo for the PawPal+ logic layer.

Runs four sections so every piece of scheduling logic is visible in the
terminal:  the daily plan, sorting and filtering, recurring tasks, and
conflict detection. Run it with:  python main.py

The planning day is fixed rather than date.today() so the output is
reproducible — the weekly grooming task is only due on Mondays.
"""

from datetime import date, time
import argparse

from pawpal_system import (
    DailyPlan,
    Frequency,
    Owner,
    Pet,
    Priority,
    Scheduler,
    Task,
)

PLANNING_DAY = date(2026, 9, 14)
LINE_WIDTH = 62


def build_demo_owner() -> Owner:
    """Create the sample owner, pets and tasks used by this demo.

    Tasks are deliberately added out of chronological order so the sorting
    methods in the second section have something real to reorder.
    """
    mochi = Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3)
    mochi.add_task(
        Task(
            "Evening walk",
            duration_minutes=25,
            priority=Priority.MEDIUM,
            preferred_time=time(18, 0),
        )
    )
    mochi.add_task(Task("Puzzle feeder", duration_minutes=15, priority=Priority.LOW))
    mochi.add_task(
        Task(
            "Morning walk",
            duration_minutes=30,
            priority=Priority.HIGH,
            preferred_time=time(8, 0),
        )
    )
    mochi.add_task(Task("Breakfast", duration_minutes=10, priority=Priority.HIGH))
    mochi.add_task(
        Task(
            "Brush coat",
            duration_minutes=20,
            priority=Priority.MEDIUM,
            frequency=Frequency.WEEKLY,
            weekly_day=0,
        )
    )

    pickle = Pet(name="Pickle", species="cat", breed="Tabby", age_years=7)
    pickle.add_task(Task("Wand play", duration_minutes=15, priority=Priority.LOW))
    pickle.add_task(
        Task(
            "Thyroid meds",
            duration_minutes=5,
            priority=Priority.HIGH,
            preferred_time=time(9, 0),
        )
    )
    pickle.add_task(Task("Clip nails", duration_minutes=25, priority=Priority.LOW))
    pickle.add_task(Task("Wet food", duration_minutes=10, priority=Priority.MEDIUM))

    owner = Owner(name="Jordan", minutes_available=90, preferences=["walk", "play"])
    owner.add_pet(mochi)
    owner.add_pet(pickle)
    return owner


def build_conflict_scenario() -> Owner:
    """Create an owner whose fixed-time tasks deliberately collide."""
    mochi = Pet(name="Mochi", species="dog")
    mochi.add_task(
        Task("Morning walk", 30, priority=Priority.HIGH, preferred_time=time(8, 0))
    )
    pickle = Pet(name="Pickle", species="cat")
    pickle.add_task(
        Task("Insulin shot", 10, priority=Priority.HIGH, preferred_time=time(8, 15))
    )
    pickle.add_task(
        Task("Eye drops", 5, priority=Priority.MEDIUM, preferred_time=time(8, 20))
    )
    owner = Owner(name="Jordan", minutes_available=90)
    owner.add_pet(mochi)
    owner.add_pet(pickle)
    return owner


def section(title: str) -> None:
    """Print a section banner."""
    print()
    print("=" * LINE_WIDTH)
    print(title.center(LINE_WIDTH))
    print("=" * LINE_WIDTH)


def print_tasks(tasks: list[Task], indent: str = "    ") -> None:
    """Print a list of tasks one per line, with fixed times where set."""
    if not tasks:
        print(f"{indent}(none)")
    for task in tasks:
        when = f"{task.preferred_time:%H:%M}" if task.is_anchored else "  --  "
        due = f"  due {task.due_date:%a %b %d}" if task.due_date else ""
        done = "  [done]" if task.completed else ""
        print(f"{indent}{when}  {task.title:<16}{task.duration_minutes:>3} min  "
              f"{task.priority:<7}{due}{done}")


# --- Section 1: the daily plan ---------------------------------------------


def print_plan(plan: DailyPlan) -> None:
    """Print one pet's plan as a timed table, then anything left out."""
    print()
    print("-" * LINE_WIDTH)
    print(plan.pet_name.upper())
    print("-" * LINE_WIDTH)

    if plan.is_empty:
        print("  Nothing scheduled today.")
    for item in plan.scheduled:
        window = f"{item.start_time:%H:%M}-{item.end_time():%H:%M}"
        print(f"  {window}  {item.task.title:<16}{item.task.duration_minutes:>3} min")
        print(f"{'':<15}{item.task.priority:<8} why: {item.reason}")

    print(f"\n  {len(plan.scheduled)} tasks, {plan.minutes_used} min of care")

    if plan.skipped:
        print("\n  Left out:")
        for item in plan.skipped:
            print(f"    - {item.task.title:<16}{item.reason}")


def show_daily_plan(owner: Owner, scheduler: Scheduler) -> None:
    """Build and print the plan for the whole household."""
    section(f"TODAY'S SCHEDULE - {PLANNING_DAY:%A, %B %d, %Y}")
    print(f"Owner:      {owner.name}")
    print(f"Time today: {owner.minutes_available} min")
    print(f"Prefers:    {', '.join(owner.preferences) or 'no preferences set'}")
    print(f"Pets:       {', '.join(str(pet) for pet in owner.pets)}")

    warnings = scheduler.conflict_warnings(owner, day=PLANNING_DAY)
    print(f"Conflicts:  {len(warnings) or 'none detected'}")

    plans = scheduler.build_plans(owner, day=PLANNING_DAY)
    for plan in plans:
        print_plan(plan)

    total_used = sum(plan.minutes_used for plan in plans)
    total_planned = sum(len(plan.scheduled) for plan in plans)
    total_skipped = sum(len(plan.skipped) for plan in plans)
    print()
    print("-" * LINE_WIDTH)
    print(
        f"  {total_planned} tasks planned, {total_skipped} left out, "
        f"{total_used}/{owner.minutes_available} min used"
    )


# --- Section 2: sorting and filtering --------------------------------------


def show_sorting_and_filtering(owner: Owner, scheduler: Scheduler) -> None:
    """Show the sort and filter helpers working on unordered input."""
    section("SORTING AND FILTERING")
    mochi = owner.get_pet("Mochi")

    print("Mochi's tasks in the order they were entered:")
    print_tasks(mochi.tasks)

    print("\nScheduler.sort_by_time() - fixed times first, unpinned tasks last:")
    print_tasks(scheduler.sort_by_time(mochi.tasks))

    print("\nScheduler.sort_by_priority() - highest priority, then shortest:")
    print_tasks(scheduler.sort_by_priority(mochi.tasks))

    print("\nOwner.filter_tasks(pet_name='Pickle') - one pet only:")
    print_tasks(owner.filter_tasks(pet_name="Pickle"))

    print("\nOwner.filter_tasks(priority='high') - across every pet:")
    print_tasks(owner.filter_tasks(priority="high"))

    print("\nOwner.filter_tasks(completed=False, due_on=PLANNING_DAY) - due today:")
    print_tasks(owner.filter_tasks(completed=False, due_on=PLANNING_DAY))
    print(
        "    ^ 'Brush coat' is weekly on Monday, so it appears here but would "
        "not\n      on any other weekday."
    )


# --- Section 3: recurring tasks --------------------------------------------


def show_recurring_tasks(owner: Owner) -> None:
    """Complete a daily and a weekly task, and show the follow-ups appear."""
    section("RECURRING TASKS")
    mochi = owner.get_pet("Mochi")

    for title in ("Breakfast", "Brush coat"):
        task = mochi.get_task(title)
        follow_up = mochi.complete_task(task, today=PLANNING_DAY)
        print(f"Completed '{title}' ({task.frequency}) on {PLANNING_DAY:%a %b %d}")
        print(f"  -> queued: {follow_up}")

    print("\nMochi's pending list now carries the next occurrences:")
    print_tasks(mochi.filter_tasks(completed=False))

    print(f"\nStill due on {PLANNING_DAY:%a %b %d} (the follow-ups are not):")
    print_tasks(mochi.tasks_due_on(PLANNING_DAY))


# --- Section 4: conflict detection -----------------------------------------


def show_conflict_detection(scheduler: Scheduler) -> None:
    """Print warnings for deliberately colliding fixed-time tasks."""
    section("CONFLICT DETECTION")
    owner = build_conflict_scenario()

    print("Three tasks pinned to overlapping times:")
    for pet in owner.pets:
        for task in pet.tasks:
            start, end = task.window_on(PLANNING_DAY)
            print(f"    {start:%H:%M}-{end:%H:%M}  {task.title:<16}({pet.name})")

    warnings = scheduler.conflict_warnings(owner, day=PLANNING_DAY)
    print(f"\nScheduler.conflict_warnings() found {len(warnings)}:")
    for warning in warnings:
        print(f"    ! {warning}")

    print("\nThe plan still builds - the loser is skipped, not crashed on:")
    for plan in scheduler.build_plans(owner, day=PLANNING_DAY):
        for item in plan.scheduled:
            print(f"    kept    {item.start_time:%H:%M}  {item.task.title} ({plan.pet_name})")
        for item in plan.skipped:
            print(f"    skipped       {item.task.title} ({plan.pet_name}) - {item.reason}")


def main() -> None:
    """Run every demo section in order."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", metavar="FILE", help="Save the final demo state as JSON")
    parser.add_argument("--load", metavar="FILE", help="Display a previously saved household")
    args = parser.parse_args()
    try:
        owner = Owner.load_from_json(args.load) if args.load else build_demo_owner()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    scheduler = Scheduler(day_start=time(8, 0), day_end=time(21, 0))

    show_daily_plan(owner, scheduler)
    section("HOUSEHOLD PRIORITY ORDER")
    print_tasks(scheduler.sort_by_priority(owner.filter_tasks(completed=False, due_on=PLANNING_DAY)))
    section("NEXT AVAILABLE SLOT")
    for duration in (10, 15):
        slot = scheduler.next_available_slot(owner, duration, PLANNING_DAY)
        print(f"  {duration} min: {slot.strftime('%H:%M') if slot else 'no slot within the shared budget'}")
    if not args.load:
        show_sorting_and_filtering(owner, scheduler)
        show_recurring_tasks(owner)
        show_conflict_detection(scheduler)
    if args.save:
        try:
            owner.save_to_json(args.save)
        except OSError as error:
            parser.error(str(error))
        print(f"\nSaved {len(owner.pets)} pets and {len(owner.all_tasks())} tasks to {args.save}")
    print()


if __name__ == "__main__":
    main()
