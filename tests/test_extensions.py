"""Regression tests for persistence, recurrence, and household slot finding."""
from datetime import date, time, timedelta
import json

import pytest
from streamlit.testing.v1 import AppTest

from main import build_demo_owner
from pawpal_system import Owner, Pet, Scheduler, Task
from test_app import APP, click

DAY = date(2026, 9, 14)


def test_snapshot_restores_types_and_identical_plans(tmp_path):
    owner = build_demo_owner()
    owner.pets[0].complete_task(owner.pets[0].get_task("Breakfast"), today=DAY)
    destination = tmp_path / "data.json"
    owner.save_to_json(destination)
    restored = Owner.load_from_json(destination)
    assert restored == owner
    assert restored is not owner
    assert Scheduler().build_plans(restored, DAY) == Scheduler().build_plans(owner, DAY)
    assert restored.pets[0].tasks[-1].due_date == DAY + timedelta(days=1)


def test_snapshot_preserves_duplicate_pet_names(tmp_path):
    owner = Owner("Sam", pets=[Pet("Mochi", "dog"), Pet("Mochi", "cat")])
    path = tmp_path / "data.json"
    owner.save_to_json(path)
    assert [p.species for p in Owner.load_from_json(path).pets] == ["dog", "cat"]


@pytest.mark.parametrize("contents", ['not json', '{}', '{"version": 99}', '{"version":1,"owner":[]}'])
def test_invalid_snapshot_is_rejected(tmp_path, contents):
    path = tmp_path / "data.json"
    path.write_text(contents)
    with pytest.raises(ValueError, match="Invalid PawPal snapshot"):
        Owner.load_from_json(path)


def test_invalid_task_status_is_rejected(tmp_path):
    path = tmp_path / "data.json"
    build_demo_owner().save_to_json(path)
    payload = json.loads(path.read_text())
    payload["owner"]["pets"][0]["tasks"][0]["completed"] = "false"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="boolean"):
        Owner.load_from_json(path)


def test_missing_snapshot_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        Owner.load_from_json(tmp_path / "missing.json")


def test_repeated_completion_does_not_duplicate_follow_up():
    pet = Pet("Mochi", "dog", tasks=[Task("Walk", 10)])
    original = pet.tasks[0]
    follow_up = pet.complete_task(original, DAY)
    assert pet.complete_task(original, DAY) is None
    assert pet.tasks == [original, follow_up]


def test_undo_after_reload_targets_exact_follow_up_even_on_another_day(tmp_path):
    pet = Pet("Mochi", "dog", tasks=[Task("Walk", 10)])
    original = pet.tasks[0]
    unrelated = Task("Walk", 10, due_date=DAY + timedelta(days=1))
    pet.add_task(unrelated)
    pet.complete_task(original, DAY)
    path = tmp_path / "data.json"
    Owner("Sam", pets=[pet]).save_to_json(path)
    restored = Owner.load_from_json(path).pets[0]
    assert restored.uncomplete_task(restored.tasks[0], DAY + timedelta(days=2))
    assert [task.task_id for task in restored.tasks] == [original.task_id, unrelated.task_id]
    assert not restored.tasks[0].completed


def test_slot_uses_all_pets_and_accepts_touching_boundaries():
    owner = Owner("Sam", 90, pets=[
        Pet("Dog", "dog", tasks=[Task("Walk", 30, preferred_time=time(8))]),
        Pet("Cat", "cat", tasks=[Task("Play", 15, preferred_time=time(8, 30))]),
    ])
    before = list(owner.all_tasks())
    assert Scheduler().next_available_slot(owner, 15, DAY) == time(8, 45)
    assert owner.all_tasks() == before


def test_slot_respects_remaining_budget():
    owner = Owner("Sam", 30, pets=[Pet("Dog", "dog", tasks=[Task("Walk", 30)])])
    assert Scheduler().next_available_slot(owner, 1, DAY) is None


def test_slot_requires_contiguous_space_and_respects_day_end():
    owner = Owner("Sam", 90, pets=[Pet("Dog", "dog", tasks=[
        Task("Walk", 20, preferred_time=time(8, 10)),
        Task("Feed", 20, preferred_time=time(8, 40)),
    ])])
    scheduler = Scheduler(day_end=time(9))
    assert scheduler.next_available_slot(owner, 10, DAY) == time(8)
    assert scheduler.next_available_slot(owner, 15, DAY) is None


@pytest.mark.parametrize("duration", [0, -1, 2.5, True])
def test_invalid_slot_duration(duration):
    with pytest.raises(ValueError):
        Scheduler().next_available_slot(Owner("Sam"), duration, DAY)


def test_empty_household_slot_starts_at_day_start():
    assert Scheduler().next_available_slot(Owner("Sam"), 60, DAY) == time(8)


def test_ui_snapshot_survives_a_new_session(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWPAL_DATA_PATH", str(tmp_path / "data.json"))
    app = AppTest.from_file(APP, default_timeout=60).run()
    click(app, "Load example data")
    click(app, "Save to JSON")
    assert not app.exception
    fresh = AppTest.from_file(APP, default_timeout=60).run()
    assert not fresh.session_state.owner.pets
    click(fresh, "Load saved data")
    assert not fresh.exception
    assert [p.name for p in fresh.session_state.owner.pets] == ["Mochi", "Pickle"]


def test_ui_failed_load_keeps_existing_household(tmp_path, monkeypatch):
    path = tmp_path / "data.json"
    path.write_text("broken")
    monkeypatch.setenv("PAWPAL_DATA_PATH", str(path))
    app = AppTest.from_file(APP, default_timeout=60).run()
    click(app, "Load example data")
    click(app, "Load saved data")
    assert not app.exception
    assert len(app.session_state.owner.pets) == 2
    assert any("Could not load" in error.value for error in app.error)


def test_conflict_resolution_uses_plan_when_priority_reverses_pair_order():
    app = AppTest.from_file(APP, default_timeout=60)
    app.session_state.owner = Owner("Sam", 60, pets=[Pet("Dog", "dog", tasks=[
        Task("Low", 10, priority="low", preferred_time=time(8)),
        Task("High", 10, priority="high", preferred_time=time(8)),
    ])])
    app.session_state.show_plan = True
    app.run()
    assert not app.exception
    assert any("keep **High** and skip **Low**" in c.value for c in app.caption)
