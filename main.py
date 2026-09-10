"""CLI demo for the PawPal+ logic layer.

Builds a sample owner, two pets and a handful of tasks, then prints the plan
the Scheduler produces. Run it with:  python main.py

The planning day is fixed rather than date.today() so the output is
reproducible — the weekly grooming task is only due on Mondays.
"""

from datetime import date, time

from pawpal_system import DailyPlan, Frequency, Owner, Pet, Priority, Scheduler, Task

PLANNING_DAY = date(2026, 9, 14)
LINE_WIDTH = 62


def build_demo_owner() -> Owner:
    """Create the sample owner, pets and tasks used by this demo."""
    mochi = Pet(name="Mochi", species="dog", breed="Shiba Inu", age_years=3)
    mochi.add_task(
        Task(
            "Morning walk",
            duration_minutes=30,
            priority=Priority.HIGH,
            preferred_time=time(8, 0),
        )
    )
    mochi.add_task(Task("Breakfast", duration_minutes=10, priority=Priority.HIGH))
    mochi.add_task(Task("Puzzle feeder", duration_minutes=15, priority=Priority.LOW))
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
    pickle.add_task(
        Task(
            "Thyroid meds",
            duration_minutes=5,
            priority=Priority.HIGH,
            preferred_time=time(9, 0),
        )
    )
    pickle.add_task(Task("Wet food", duration_minutes=10, priority=Priority.MEDIUM))
    pickle.add_task(Task("Wand play", duration_minutes=15, priority=Priority.LOW))
    pickle.add_task(Task("Clip nails", duration_minutes=25, priority=Priority.LOW))

    owner = Owner(name="Jordan", minutes_available=90, preferences=["walk", "play"])
    owner.add_pet(mochi)
    owner.add_pet(pickle)
    return owner


def print_header(owner: Owner, day: date) -> None:
    """Print the report banner with the owner's constraints for the day."""
    print("=" * LINE_WIDTH)
    print(f"TODAY'S SCHEDULE - {day:%A, %B %d, %Y}".center(LINE_WIDTH))
    print("=" * LINE_WIDTH)
    print(f"Owner:      {owner.name}")
    print(f"Time today: {owner.minutes_available} min")
    print(f"Prefers:    {', '.join(owner.preferences) or 'no preferences set'}")
    print(f"Pets:       {', '.join(str(pet) for pet in owner.pets)}")


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


def main() -> None:
    """Build the demo data, plan the day, and print the result."""
    owner = build_demo_owner()
    scheduler = Scheduler(day_start=time(8, 0), day_end=time(21, 0))

    print_header(owner, PLANNING_DAY)
    plans = scheduler.build_plans(owner, day=PLANNING_DAY)
    for plan in plans:
        print_plan(plan)

    total_used = sum(plan.minutes_used for plan in plans)
    total_scheduled = sum(len(plan.scheduled) for plan in plans)
    total_skipped = sum(len(plan.skipped) for plan in plans)

    print()
    print("=" * LINE_WIDTH)
    print(
        f"  {total_scheduled} tasks planned, {total_skipped} left out, "
        f"{total_used}/{owner.minutes_available} min used"
    )
    print("=" * LINE_WIDTH)


if __name__ == "__main__":
    main()
