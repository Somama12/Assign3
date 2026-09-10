"""PawPal+ logic layer.

Class skeletons generated from diagrams/uml.mmd. No behavior yet — every method
body is a stub so the shape of the system can be reviewed before implementation.
"""

from dataclasses import dataclass, field
from datetime import time
from enum import IntEnum


class Priority(IntEnum):
    """How important a task is. Higher value sorts first."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass
class Task:
    """One unit of pet care, e.g. a 30 minute morning walk."""

    title: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    completed: bool = False

    def mark_complete(self) -> None:
        """Flag this task as done for the day."""
        raise NotImplementedError


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
        raise NotImplementedError

    def remove_task(self, task_title: str) -> bool:
        """Drop a task by title. Returns True if something was removed."""
        raise NotImplementedError

    def pending_tasks(self) -> list[Task]:
        """Return only the tasks that are not yet completed."""
        raise NotImplementedError


@dataclass
class Owner:
    """The person using PawPal+, including the constraints they bring."""

    name: str
    minutes_available: int = 60
    preferences: list[str] = field(default_factory=list)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet with this owner."""
        raise NotImplementedError

    def remove_pet(self, pet_name: str) -> bool:
        """Drop a pet by name. Returns True if something was removed."""
        raise NotImplementedError

    def get_pet(self, pet_name: str) -> Pet | None:
        """Look up one of this owner's pets by name."""
        raise NotImplementedError


@dataclass
class ScheduledTask:
    """A task that made the cut, pinned to a clock time."""

    task: Task
    start_time: time

    def end_time(self) -> time:
        """When this task finishes, based on its duration."""
        raise NotImplementedError


@dataclass
class DailyPlan:
    """The scheduler's answer for one pet: what happens, and what didn't fit."""

    pet_name: str
    scheduled: list[ScheduledTask] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    minutes_used: int = 0

    def minutes_remaining(self, budget: int) -> int:
        """How much of the owner's time budget this plan leaves unused."""
        raise NotImplementedError


class Scheduler:
    """Turns pending tasks into a plan that fits the owner's day."""

    def __init__(self, day_start: time = time(8, 0)) -> None:
        self.day_start = day_start

    def build_plan(self, owner: Owner, pet: Pet) -> DailyPlan:
        """Choose and order one pet's tasks within the owner's time budget."""
        raise NotImplementedError

    def build_plans(self, owner: Owner) -> list[DailyPlan]:
        """Plan every pet the owner has, sharing the one time budget."""
        raise NotImplementedError

    def explain(self, plan: DailyPlan) -> str:
        """Describe in plain language why the plan looks the way it does."""
        raise NotImplementedError
