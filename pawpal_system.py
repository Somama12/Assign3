"""PawPal+ logic layer.

The "brain" of the app, with no Streamlit imports so it can be driven from the
terminal (see main.py) and tested directly (see tests/test_pawpal.py).

Data model:  Owner -> Pet -> Task
Planning:    Scheduler reads an Owner's constraints and each Pet's due tasks,
             and returns a DailyPlan of ScheduledTask / SkippedTask entries.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum, IntEnum


class Priority(IntEnum):
    """How important a task is. Higher value means it gets scheduled first."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @classmethod
    def parse(cls, value: "Priority | int | str") -> "Priority":
        """Accept a Priority, an int, or a string like 'high' from the UI."""
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        try:
            return cls[str(value).strip().upper()]
        except KeyError:
            raise ValueError(f"unknown priority: {value!r}") from None

    def __str__(self) -> str:
        """Show the name in lowercase, e.g. 'high'."""
        return self.name.lower()

    def __format__(self, format_spec: str) -> str:
        """Format as the lowercase name, since IntEnum would show the number."""
        if format_spec and format_spec[-1] in "bcdoxXneEfFgG%":
            return int.__format__(self, format_spec)
        return format(str(self), format_spec)


class Frequency(str, Enum):
    """How often a task comes around."""

    DAILY = "daily"
    WEEKLY = "weekly"

    @classmethod
    def parse(cls, value: "Frequency | str") -> "Frequency":
        """Accept a Frequency or a string like 'Weekly' from the UI."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            raise ValueError(f"unknown frequency: {value!r}") from None

    def __str__(self) -> str:
        """Show the underlying value, e.g. 'daily'."""
        return self.value


@dataclass
class Task:
    """One unit of pet care, e.g. a 30 minute morning walk."""

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    frequency: Frequency = Frequency.DAILY
    weekly_day: int = 0
    preferred_time: time | None = None
    completed: bool = False

    def __post_init__(self) -> None:
        """Validate the duration and accept plain strings for the enum fields."""
        if self.duration_minutes <= 0:
            raise ValueError(
                f"{self.title!r}: duration_minutes must be positive, "
                f"got {self.duration_minutes}"
            )
        self.priority = Priority.parse(self.priority)
        self.frequency = Frequency.parse(self.frequency)
        if not 0 <= self.weekly_day <= 6:
            raise ValueError(
                f"{self.title!r}: weekly_day must be 0 (Monday) through 6, "
                f"got {self.weekly_day}"
            )

    @property
    def duration(self) -> timedelta:
        """The duration as a timedelta, for time arithmetic."""
        return timedelta(minutes=self.duration_minutes)

    @property
    def is_anchored(self) -> bool:
        """True if this task must happen at a specific clock time."""
        return self.preferred_time is not None

    def mark_complete(self) -> None:
        """Flag this task as done."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Flag this task as not done, e.g. when a new day starts."""
        self.completed = False

    def is_due_on(self, day: date) -> bool:
        """True if this task needs doing on the given day."""
        if self.frequency is Frequency.DAILY:
            return True
        return day.weekday() == self.weekly_day

    def __str__(self) -> str:
        """One-line description, e.g. 'Morning walk (30 min, high)'."""
        return f"{self.title} ({self.duration_minutes} min, {self.priority})"


@dataclass
class Pet:
    """A single animal in the owner's care, plus the tasks it needs."""

    name: str
    species: str
    breed: str = ""
    age_years: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a care task to this pet."""
        self.tasks.append(task)

    def remove_task(self, task_title: str) -> bool:
        """Drop the first task with this title. True if one was removed."""
        for index, task in enumerate(self.tasks):
            if task.title == task_title:
                del self.tasks[index]
                return True
        return False

    def get_task(self, task_title: str) -> Task | None:
        """Look up one of this pet's tasks by title."""
        return next((t for t in self.tasks if t.title == task_title), None)

    def pending_tasks(self) -> list[Task]:
        """Return only the tasks that are not yet completed."""
        return [t for t in self.tasks if not t.completed]

    def completed_tasks(self) -> list[Task]:
        """Return only the tasks that are already done."""
        return [t for t in self.tasks if t.completed]

    def tasks_due_on(self, day: date) -> list[Task]:
        """Return the pending tasks that need doing on the given day."""
        return [t for t in self.pending_tasks() if t.is_due_on(day)]

    def minutes_needed_on(self, day: date) -> int:
        """Total minutes this pet's due tasks would take if all were done."""
        return sum(t.duration_minutes for t in self.tasks_due_on(day))

    def __str__(self) -> str:
        """One-line description, e.g. 'Mochi (dog, Shiba Inu, 3y)'."""
        details = [self.species]
        if self.breed:
            details.append(self.breed)
        if self.age_years:
            details.append(f"{self.age_years}y")
        return f"{self.name} ({', '.join(details)})"


@dataclass
class Owner:
    """The person using PawPal+, and the constraints they bring to the day."""

    name: str
    minutes_available: int = 60
    preferences: list[str] = field(default_factory=list)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet with this owner."""
        self.pets.append(pet)

    def remove_pet(self, pet_name: str) -> bool:
        """Drop the first pet with this name. True if one was removed."""
        for index, pet in enumerate(self.pets):
            if pet.name == pet_name:
                del self.pets[index]
                return True
        return False

    def get_pet(self, pet_name: str) -> Pet | None:
        """Look up one of this owner's pets by name."""
        return next((p for p in self.pets if p.name == pet_name), None)

    def all_tasks(self) -> list[Task]:
        """Every task across every pet, for summaries and counts."""
        return [task for pet in self.pets for task in pet.tasks]

    def tasks_by_pet(self) -> dict[str, list[Task]]:
        """Every task grouped by pet name, so callers keep the owning pet."""
        return {pet.name: list(pet.tasks) for pet in self.pets}

    def prefers(self, task: Task) -> bool:
        """True if any of this owner's preference keywords match the task."""
        title = task.title.lower()
        return any(p.strip().lower() in title for p in self.preferences if p.strip())

    def __str__(self) -> str:
        """One-line description, e.g. 'Jordan (90 min today, 2 pets)'."""
        return (
            f"{self.name} ({self.minutes_available} min today, "
            f"{len(self.pets)} pet{'s' if len(self.pets) != 1 else ''})"
        )


@dataclass
class ScheduledTask:
    """A task that made the cut, pinned to a clock time with the reason why."""

    task: Task
    start_time: time
    reason: str = ""

    def end_time(self) -> time:
        """When this task finishes, based on its duration."""
        start = datetime.combine(date.min, self.start_time)
        return (start + self.task.duration).time()

    def __str__(self) -> str:
        """One-line row, e.g. '08:00-08:30  Morning walk (30 min, high)'."""
        return (
            f"{self.start_time:%H:%M}-{self.end_time():%H:%M}  {self.task}"
        )


@dataclass
class SkippedTask:
    """A task that did not fit, and the reason it was left out."""

    task: Task
    reason: str

    def __str__(self) -> str:
        """One-line row, e.g. 'Grooming (45 min, low) - out of time'."""
        return f"{self.task} - {self.reason}"


@dataclass
class DailyPlan:
    """The scheduler's answer for one pet: what happens, and what didn't fit."""

    pet_name: str
    day: date
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)
    budget_minutes: int = 0

    @property
    def minutes_used(self) -> int:
        """Total minutes claimed by the scheduled tasks."""
        return sum(item.task.duration_minutes for item in self.scheduled)

    @property
    def minutes_remaining(self) -> int:
        """How much of the time budget this plan leaves unused."""
        return max(0, self.budget_minutes - self.minutes_used)

    @property
    def is_empty(self) -> bool:
        """True if nothing at all got scheduled."""
        return not self.scheduled


class Scheduler:
    """Turns each pet's due tasks into a plan that fits the owner's day.

    Rules, in order:
      1. Only pending tasks that are due on the planning day are considered.
      2. Tasks with a preferred_time claim that exact slot first.
      3. Remaining tasks fill the open gaps, highest priority first; within the
         same priority, tasks matching the owner's preferences go first, then
         shorter tasks, so more of the day's list gets done.
      4. Nothing is scheduled past the end of the day or over the time budget.

    Every pet is planned against ONE shared clock and ONE shared budget: the
    owner has a single pair of hands, so two pets' tasks must never overlap,
    and a high priority task for pet B outranks a low priority task for pet A.
    """

    def __init__(self, day_start: time = time(8, 0), day_end: time = time(21, 0)) -> None:
        """Set the clock window the scheduler is allowed to place tasks in."""
        if day_end <= day_start:
            raise ValueError("day_end must be later than day_start")
        self.day_start = day_start
        self.day_end = day_end

    def build_plan(self, owner: Owner, pet: Pet, day: date | None = None) -> DailyPlan:
        """Plan one pet's day against the owner's full time budget."""
        day = day or date.today()
        candidates = [(pet, task) for task in pet.tasks_due_on(day)]
        plans = self._pack(owner, day, candidates, [pet])
        return plans[0]

    def build_plans(self, owner: Owner, day: date | None = None) -> list[DailyPlan]:
        """Plan every pet at once, sharing one timeline and one time budget."""
        day = day or date.today()
        candidates = [
            (pet, task) for pet in owner.pets for task in pet.tasks_due_on(day)
        ]
        return self._pack(owner, day, candidates, owner.pets)

    def _pack(
        self,
        owner: Owner,
        day: date,
        candidates: list[tuple[Pet, Task]],
        pets: list[Pet],
    ) -> list[DailyPlan]:
        """Fit the candidate (pet, task) pairs into the day, then group by pet."""
        budget = owner.minutes_available
        plans = {
            pet.name: DailyPlan(pet_name=pet.name, day=day, budget_minutes=budget)
            for pet in pets
        }
        busy: list[tuple[datetime, datetime]] = []
        used = 0

        anchored = sorted(
            (pair for pair in candidates if pair[1].is_anchored),
            key=lambda pair: (pair[1].preferred_time, -int(pair[1].priority)),
        )
        flexible = sorted(
            (pair for pair in candidates if not pair[1].is_anchored),
            key=lambda pair: (
                -int(pair[1].priority),
                not owner.prefers(pair[1]),
                pair[1].duration_minutes,
            ),
        )

        for pet, task in anchored:
            plan = plans[pet.name]
            start = datetime.combine(day, task.preferred_time)
            end = start + task.duration
            if used + task.duration_minutes > budget:
                plan.skipped.append(
                    SkippedTask(task, self._budget_reason(task, budget, used))
                )
            elif start < datetime.combine(day, self.day_start) or end > datetime.combine(
                day, self.day_end
            ):
                plan.skipped.append(
                    SkippedTask(
                        task,
                        f"its {task.preferred_time:%H:%M} slot falls outside the "
                        f"{self.day_start:%H:%M}-{self.day_end:%H:%M} day",
                    )
                )
            elif any(start < b_end and b_start < end for b_start, b_end in busy):
                plan.skipped.append(
                    SkippedTask(task, "its preferred time overlaps an earlier task")
                )
            else:
                busy.append((start, end))
                used += task.duration_minutes
                plan.scheduled.append(
                    ScheduledTask(
                        task,
                        task.preferred_time,
                        f"fixed {task.preferred_time:%H:%M} slot you asked for",
                    )
                )

        for pet, task in flexible:
            plan = plans[pet.name]
            if used + task.duration_minutes > budget:
                plan.skipped.append(
                    SkippedTask(task, self._budget_reason(task, budget, used))
                )
                continue
            start = self._first_open_slot(day, busy, task.duration)
            if start is None:
                plan.skipped.append(
                    SkippedTask(task, "no open slot left in the day that it fits into")
                )
                continue
            busy.append((start, start + task.duration))
            used += task.duration_minutes
            plan.scheduled.append(
                ScheduledTask(task, start.time(), self._fit_reason(owner, task))
            )

        for plan in plans.values():
            plan.scheduled.sort(key=lambda item: item.start_time)
        return [plans[pet.name] for pet in pets]

    def _first_open_slot(
        self, day: date, busy: list[tuple[datetime, datetime]], duration: timedelta
    ) -> datetime | None:
        """Earliest start time that fits the duration without overlapping busy time."""
        cursor = datetime.combine(day, self.day_start)
        day_end = datetime.combine(day, self.day_end)
        for start, end in sorted(busy):
            if start - cursor >= duration:
                return cursor
            cursor = max(cursor, end)
        return cursor if day_end - cursor >= duration else None

    def _budget_reason(self, task: Task, budget: int, used: int) -> str:
        """Explain that a task was dropped for lack of time."""
        left = budget - used
        if left <= 0:
            return f"your {budget} min for the day was already full"
        return f"needs {task.duration_minutes} min, only {left} min left of your {budget}"

    def _fit_reason(self, owner: Owner, task: Task) -> str:
        """Explain why a flexible task earned its slot."""
        reason = f"{task.priority} priority"
        if owner.prefers(task):
            reason += ", and matches your preferences"
        return reason

    def explain(self, plan: DailyPlan) -> str:
        """Describe in plain language why a plan looks the way it does."""
        lines = [f"Plan for {plan.pet_name} on {plan.day:%a %b %d}:"]
        if plan.is_empty:
            lines.append("  Nothing scheduled.")
        for item in plan.scheduled:
            lines.append(f"  {item}")
            lines.append(f"      why: {item.reason}")
        lines.append(
            f"  Uses {plan.minutes_used} of {plan.budget_minutes} min "
            f"({plan.minutes_remaining} min free)."
        )
        if plan.skipped:
            lines.append("  Left out:")
            lines.extend(f"    {item}" for item in plan.skipped)
        return "\n".join(lines)
