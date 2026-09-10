"""PawPal+ logic layer.

Class skeletons generated from diagrams/uml.mmd. No behavior yet — every method
body is a stub so the shape of the system can be reviewed before implementation.
"""

from dataclasses import dataclass, field


@dataclass
class Task:
    """One unit of pet care, e.g. a 30 minute morning walk."""

    title: str
    duration_minutes: int
    priority: str = "medium"
    completed: bool = False

    def mark_complete(self) -> None:
        """Flag this task as done for the day."""
        raise NotImplementedError

    def priority_rank(self) -> int:
        """Return a sortable number so high priority tasks come first."""
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


class Scheduler:
    """Turns a pet's pending tasks into a plan that fits the owner's day."""

    def __init__(self, minutes_available: int) -> None:
        self.minutes_available = minutes_available

    def build_plan(self, pet: Pet) -> list[Task]:
        """Choose and order tasks for the day within the time budget."""
        raise NotImplementedError

    def explain_plan(self, plan: list[Task]) -> str:
        """Describe in plain language why the plan looks the way it does."""
        raise NotImplementedError
