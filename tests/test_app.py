"""Smoke tests for the Streamlit UI in app.py.

These drive the real script through Streamlit's AppTest harness, so they catch
the class of bug the logic-layer tests cannot: duplicate widget keys, state
that does not survive a rerun, and controls wired to the wrong object.
"""

from datetime import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pawpal_system import Owner, Pet, Priority, Task

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def make_app() -> AppTest:
    """Return an un-run AppTest pointed at the real app.py."""
    return AppTest.from_file(APP, default_timeout=60)


def click(app: AppTest, label: str) -> AppTest:
    """Click the button with this visible label and rerun the script."""
    return next(b for b in app.button if b.label == label).click().run()


def field(group, label):
    """Return the widget in this group with the given label."""
    return next(w for w in group if w.label == label)


def test_app_starts_without_error() -> None:
    """The script runs top to bottom on a cold session."""
    app = make_app().run()

    assert not app.exception
    assert app.title[0].value == "🐾 PawPal+"


def test_adding_a_pet_creates_a_pet_object_that_survives_a_rerun() -> None:
    """The Phase 3 checkpoint: a pet added in the browser stays in memory."""
    app = make_app().run()
    field(app.text_input, "Name").set_value("Biscuit")
    field(app.text_input, "Breed (optional)").set_value("Golden Retriever")

    app = click(app, "Add pet")

    pets = app.session_state.owner.pets
    assert [type(p).__name__ for p in pets] == ["Pet"]
    assert pets[0].name == "Biscuit"

    # An unrelated interaction must not wipe the pet.
    app = click(app, "Generate schedule")
    assert [p.name for p in app.session_state.owner.pets] == ["Biscuit"]


def test_duplicate_pet_name_is_rejected() -> None:
    """Two pets with the same name would be ambiguous in the UI, so it is blocked."""
    app = make_app()
    app.session_state.owner = Owner("Jordan", 90, pets=[Pet("Mochi", "dog")])
    app.run()
    field(app.text_input, "Name").set_value("Mochi")

    app = click(app, "Add pet")

    assert len(app.session_state.owner.pets) == 1
    assert any("already have a pet named" in e.value for e in app.error)


def test_adding_a_task_attaches_it_to_the_chosen_pet() -> None:
    """The task form calls Pet.add_task on the selected pet."""
    app = make_app()
    app.session_state.owner = Owner("Jordan", 90, pets=[Pet("Mochi", "dog")])
    app.run()
    field(app.text_input, "Task").set_value("Morning walk")
    field(app.number_input, "Minutes").set_value(30)
    field(app.selectbox, "Priority").set_value("high")

    app = click(app, "Add task")

    tasks = app.session_state.owner.pets[0].tasks
    assert len(tasks) == 1
    assert tasks[0].title == "Morning walk"
    assert tasks[0].priority is Priority.HIGH


def test_tasks_sharing_a_title_do_not_break_the_page() -> None:
    """Duplicate titles once crashed with StreamlitDuplicateElementKey."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 20))
    pet.add_task(Task("Walk", 30))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])

    app.run()

    assert not app.exception


def test_removing_a_row_removes_that_row_not_its_twin() -> None:
    """The ✕ on the first of two same-titled tasks removes the first."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Walk", 20))
    pet.add_task(Task("Walk", 30))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])
    app.run()

    app = app.button(key="rm_task_0_0").click().run()

    assert [t.duration_minutes for t in app.session_state.owner.pets[0].tasks] == [30]


def test_toggling_done_after_a_delete_hits_the_right_task() -> None:
    """Shifted indices must not complete the wrong task."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    for title in ("Walk", "Feed", "Meds"):
        pet.add_task(Task(title, 10))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])
    app.run()

    app = app.button(key="rm_task_0_0").click().run()   # delete "Walk"
    app = app.button(key="toggle_0_0").click().run()    # row 0 is now "Feed"

    completed = [t.title for t in app.session_state.owner.pets[0].tasks if t.completed]
    assert completed == ["Feed"]


def test_done_queues_the_next_occurrence_and_undo_takes_it_back() -> None:
    """The recurring-task path is reachable from the UI."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Morning walk", 30))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])
    app.run()

    app = app.button(key="toggle_0_0").click().run()
    tasks = app.session_state.owner.pets[0].tasks
    assert len(tasks) == 2
    assert tasks[1].due_date is not None
    assert any("is back on" in s.value for s in app.success)

    app = app.button(key="toggle_0_0").click().run()
    assert len(app.session_state.owner.pets[0].tasks) == 1


def test_conflicting_fixed_times_show_a_warning() -> None:
    """Conflict warnings reach the page rather than staying in the logic layer."""
    app = make_app()
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, priority=Priority.HIGH, preferred_time=time(8, 0)))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Insulin", 10, priority=Priority.HIGH, preferred_time=time(8, 15)))
    app.session_state.owner = Owner("Jordan", 90, pets=[mochi, pickle])
    app.session_state.show_plan = True

    app.run()

    assert any("two places at once" in w.value for w in app.warning)


def test_example_data_renders_a_plan() -> None:
    """Loading the demo data produces a rendered schedule with metrics."""
    app = make_app().run()

    app = click(app, "Load example data")

    assert not app.exception
    assert [m.label for m in app.metric] == ["Tasks planned", "Minutes used", "Left out"]
    assert len(app.table) == 2  # one table per pet


def test_clearing_keeps_the_owner_but_drops_the_pets() -> None:
    """Clear wipes pets and tasks without losing the owner's constraints."""
    app = make_app().run()
    app = click(app, "Load example data")

    app = click(app, "Clear pets and tasks")

    assert app.session_state.owner.pets == []
    assert app.session_state.owner.name == "Jordan"


def test_schedule_warns_when_there_is_nothing_to_plan() -> None:
    """Generating a schedule with no tasks explains itself instead of failing."""
    app = make_app().run()

    app = click(app, "Generate schedule")

    assert not app.exception
    assert any("no tasks to schedule" in w.value for w in app.warning)


def _visible_titles(app: AppTest, titles: tuple[str, ...]) -> list[str]:
    """Return the task titles in the order the page rendered them."""
    return [
        next(t for t in titles if block.value.startswith(t))
        for block in app.markdown
        if any(block.value.startswith(t) for t in titles)
    ]


def test_order_by_control_uses_the_scheduler_sort_methods() -> None:
    """The Order by control reorders rows via sort_by_time / sort_by_priority."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Evening walk", 25, priority=Priority.MEDIUM, preferred_time=time(18, 0)))
    pet.add_task(Task("Puzzle feeder", 15, priority=Priority.LOW))
    pet.add_task(Task("Morning walk", 30, priority=Priority.HIGH, preferred_time=time(8, 0)))
    pet.add_task(Task("Breakfast", 10, priority=Priority.HIGH))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])
    app.run()
    titles = ("Evening walk", "Puzzle feeder", "Morning walk", "Breakfast")

    app.radio[1].set_value("Entered").run()
    assert _visible_titles(app, titles) == list(titles)

    # By time: pinned tasks in clock order, unpinned keeping entry order.
    app.radio[1].set_value("Time").run()
    assert _visible_titles(app, titles) == [
        "Morning walk",
        "Evening walk",
        "Puzzle feeder",
        "Breakfast",
    ]

    # By priority: high first, shortest breaking the tie.
    app.radio[1].set_value("Priority").run()
    assert _visible_titles(app, titles) == [
        "Breakfast",
        "Morning walk",
        "Evening walk",
        "Puzzle feeder",
    ]


def test_reordering_does_not_break_removal() -> None:
    """With rows sorted, ✕ still deletes the task the row belongs to."""
    app = make_app()
    pet = Pet("Mochi", "dog")
    pet.add_task(Task("Late", 10, preferred_time=time(18, 0)))
    pet.add_task(Task("Early", 10, preferred_time=time(8, 0)))
    app.session_state.owner = Owner("Jordan", 90, pets=[pet])
    app.run()
    app.radio[1].set_value("Time").run()

    # "Early" is displayed first but is index 1 in pet.tasks.
    app = app.button(key="rm_task_0_1").click().run()

    assert [t.title for t in app.session_state.owner.pets[0].tasks] == ["Late"]


def test_conflict_block_says_what_the_scheduler_decided() -> None:
    """A conflict warning is paired with the resolution the owner can act on."""
    app = make_app()
    mochi = Pet("Mochi", "dog")
    mochi.add_task(Task("Morning walk", 30, priority=Priority.HIGH, preferred_time=time(8, 0)))
    pickle = Pet("Pickle", "cat")
    pickle.add_task(Task("Insulin", 10, priority=Priority.HIGH, preferred_time=time(8, 15)))
    app.session_state.owner = Owner("Jordan", 90, pets=[mochi, pickle])
    app.session_state.show_plan = True

    app.run()

    assert any("two places at once" in w.value for w in app.warning)
    assert any(
        "keep **Morning walk** and skip **Insulin**" in c.value for c in app.caption
    )
