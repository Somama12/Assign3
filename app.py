"""PawPal+ Streamlit UI.

This file is only a bridge: it collects input, hands it to the logic layer in
pawpal_system.py, and renders whatever comes back. No scheduling rules live
here, which is why the same logic runs unchanged from main.py and the tests.

Streamlit re-runs this script top to bottom on every interaction, so the Owner
object lives in st.session_state rather than being rebuilt (and emptied) each
time. Everything else is derived from that one object.
"""

from datetime import time

import streamlit as st

from main import build_demo_owner
from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")


# --- Session state ----------------------------------------------------------


def get_owner() -> Owner:
    """Return the Owner for this session, creating it on the first run only."""
    if "owner" not in st.session_state:
        st.session_state.owner = Owner(name="Jordan", minutes_available=90)
    return st.session_state.owner


def load_demo_data() -> None:
    """Replace the session's Owner with the sample data from main.py."""
    st.session_state.owner = build_demo_owner()
    st.session_state.show_plan = True


def reset_data() -> None:
    """Clear the session's pets and tasks back to an empty Owner."""
    owner = get_owner()
    st.session_state.owner = Owner(
        name=owner.name,
        minutes_available=owner.minutes_available,
        preferences=list(owner.preferences),
    )
    st.session_state.show_plan = False


owner = get_owner()
st.session_state.setdefault("show_plan", False)


# --- Owner constraints (sidebar) -------------------------------------------

st.sidebar.header("Your day")

with st.sidebar.form("owner_form"):
    name = st.text_input("Your name", value=owner.name)
    minutes = st.number_input(
        "Minutes you have today", min_value=0, max_value=720, value=owner.minutes_available, step=5
    )
    prefs = st.text_input(
        "Preferences (comma separated)",
        value=", ".join(owner.preferences),
        help="Keywords matched against task titles. These break ties between "
        "tasks of equal priority — they never outrank a higher priority task.",
    )
    col_start, col_end = st.columns(2)
    with col_start:
        day_start = st.time_input("Day starts", value=st.session_state.get("day_start", time(8, 0)))
    with col_end:
        day_end = st.time_input("Day ends", value=st.session_state.get("day_end", time(21, 0)))

    if st.form_submit_button("Save", use_container_width=True):
        if day_end <= day_start:
            st.sidebar.error("Day must end after it starts.")
        else:
            owner.name = name.strip() or owner.name
            owner.minutes_available = int(minutes)
            owner.preferences = [p.strip() for p in prefs.split(",") if p.strip()]
            st.session_state.day_start = day_start
            st.session_state.day_end = day_end
            st.sidebar.success("Saved.")

st.sidebar.divider()
st.sidebar.button("Load example data", on_click=load_demo_data, use_container_width=True)
st.sidebar.button("Clear pets and tasks", on_click=reset_data, use_container_width=True)


# --- Header -----------------------------------------------------------------

st.title("🐾 PawPal+")
st.caption(f"{owner} · {len(owner.all_tasks())} tasks on the books")

if not owner.pets:
    st.info("Add a pet below to get started, or load the example data from the sidebar.")


# --- Add a pet --------------------------------------------------------------

with st.expander("Add a pet", expanded=not owner.pets):
    with st.form("pet_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            pet_name = st.text_input("Name")
            breed = st.text_input("Breed (optional)")
        with col2:
            species = st.selectbox("Species", ["dog", "cat", "other"])
            age = st.number_input("Age (years)", min_value=0, max_value=40, value=0)

        if st.form_submit_button("Add pet"):
            if not pet_name.strip():
                st.error("Give your pet a name.")
            elif owner.get_pet(pet_name.strip()):
                st.error(f"You already have a pet named {pet_name.strip()}.")
            else:
                owner.add_pet(
                    Pet(
                        name=pet_name.strip(),
                        species=species,
                        breed=breed.strip(),
                        age_years=int(age),
                    )
                )
                st.success(f"Added {pet_name.strip()}.")


# --- Add a task -------------------------------------------------------------

if owner.pets:
    with st.expander("Add a care task", expanded=not owner.all_tasks()):
        with st.form("task_form", clear_on_submit=True):
            target_pet = st.selectbox("For which pet?", [p.name for p in owner.pets])
            title = st.text_input("Task", placeholder="Morning walk")

            col1, col2, col3 = st.columns(3)
            with col1:
                duration = st.number_input("Minutes", min_value=1, max_value=240, value=20)
            with col2:
                priority = st.selectbox("Priority", ["high", "medium", "low"], index=1)
            with col3:
                frequency = st.selectbox("Repeats", ["daily", "weekly"])

            weekly_day = st.selectbox(
                "On which day? (weekly tasks only)", WEEKDAYS, disabled=frequency != "weekly"
            )

            fixed = st.checkbox("This has to happen at a specific time")
            preferred = st.time_input("At", value=time(9, 0), disabled=not fixed)

            if st.form_submit_button("Add task"):
                pet = owner.get_pet(target_pet)
                if not title.strip():
                    st.error("Give the task a title.")
                elif pet is None:
                    st.error("That pet no longer exists.")
                else:
                    try:
                        pet.add_task(
                            Task(
                                title=title.strip(),
                                duration_minutes=int(duration),
                                priority=Priority.parse(priority),
                                frequency=Frequency.parse(frequency),
                                weekly_day=WEEKDAYS.index(weekly_day),
                                preferred_time=preferred if fixed else None,
                            )
                        )
                        st.success(f"Added '{title.strip()}' for {pet.name}.")
                    except ValueError as error:
                        st.error(str(error))


# --- Current pets and tasks -------------------------------------------------

if owner.pets:
    st.divider()
    st.subheader("Pets and tasks")

    if st.session_state.get("last_follow_up"):
        st.success(f"Done — {st.session_state.pop('last_follow_up')}")

    show = st.radio(
        "Show",
        ["All", "Pending", "Done"],
        horizontal=True,
        label_visibility="collapsed",
    )
    status = {"All": None, "Pending": False, "Done": True}[show]

    # Widget keys and removals use list position, not the name/title: two tasks
    # may legitimately share a title (a morning and an evening "Walk"), and
    # keying on the title both collides and deletes the wrong row.
    for pet_index, pet in enumerate(list(owner.pets)):
        with st.container(border=True):
            header, remove = st.columns([5, 1])
            header.markdown(f"**{pet}**")
            if remove.button("Remove", key=f"rm_pet_{pet_index}"):
                owner.remove_pet_at(pet_index)
                st.rerun()

            if not pet.tasks:
                st.caption("No tasks yet.")
                continue

            visible = pet.filter_tasks(completed=status)
            if not visible:
                st.caption(f"No {show.lower()} tasks.")
                continue

            # enumerate the full list so keys and removals stay aligned with
            # the real positions, then skip the rows the filter excludes.
            for task_index, task in enumerate(list(pet.tasks)):
                if not any(task is shown for shown in visible):
                    continue
                done_col, text_col, drop_col = st.columns([1.4, 6, 1])

                # A button rather than a checkbox: checkbox state sticks to its
                # key, so after a row is deleted the shifted indices would make
                # a checkbox inherit the deleted row's state and complete the
                # wrong task. Button presses do not persist across reruns.
                if done_col.button(
                    "Undo" if task.completed else "Done",
                    key=f"toggle_{pet_index}_{task_index}",
                ):
                    # complete_task queues the next occurrence; uncomplete_task
                    # takes it back off the list again.
                    if task.completed:
                        pet.uncomplete_task(task)
                    else:
                        follow_up = pet.complete_task(task)
                        st.session_state.last_follow_up = (
                            f"'{follow_up.title}' is back on "
                            f"{follow_up.due_date:%a %b %d}."
                        )
                    st.rerun()

                recurrence = (
                    "daily" if task.frequency is Frequency.DAILY
                    else f"weekly on {WEEKDAYS[task.weekly_day]}"
                )
                when = f" · at {task.preferred_time:%H:%M}" if task.is_anchored else ""
                due = f" · due {task.due_date:%a %b %d}" if task.due_date else ""
                label = (
                    f"{task.title} — {task.duration_minutes} min · "
                    f"{task.priority} · {recurrence}{when}{due}"
                )
                text_col.markdown(f"~~{label}~~" if task.completed else label)

                if drop_col.button("✕", key=f"rm_task_{pet_index}_{task_index}"):
                    pet.remove_task_at(task_index)
                    st.rerun()


# --- Build the schedule -----------------------------------------------------

st.divider()
st.subheader("Today's plan")

col_day, col_button = st.columns([2, 1])
plan_day = col_day.date_input("Plan for", value="today")
if col_button.button("Generate schedule", type="primary", use_container_width=True):
    st.session_state.show_plan = True

if st.session_state.show_plan:
    if not owner.all_tasks():
        st.warning("There are no tasks to schedule yet.")
    else:
        # Built fresh on every run, so edits above are always reflected below.
        scheduler = Scheduler(
            day_start=st.session_state.get("day_start", time(8, 0)),
            day_end=st.session_state.get("day_end", time(21, 0)),
        )
        # Warn before planning: the scheduler resolves overlaps by skipping the
        # loser, which is safe but silent, so the owner should see the clash.
        warnings = scheduler.conflict_warnings(owner, day=plan_day)
        for warning in warnings:
            st.warning(warning, icon="⚠️")

        plans = scheduler.build_plans(owner, day=plan_day)

        total_used = sum(plan.minutes_used for plan in plans)
        total_planned = sum(len(plan.scheduled) for plan in plans)
        total_skipped = sum(len(plan.skipped) for plan in plans)

        met1, met2, met3 = st.columns(3)
        met1.metric("Tasks planned", total_planned)
        met2.metric("Minutes used", f"{total_used}/{owner.minutes_available}")
        met3.metric("Left out", total_skipped)

        for plan in plans:
            st.markdown(f"#### {plan.pet_name}")

            if plan.is_empty:
                st.caption("Nothing scheduled today.")
            else:
                st.table(
                    [
                        {
                            "When": f"{item.start_time:%H:%M}–{item.end_time():%H:%M}",
                            "Task": item.task.title,
                            "Min": item.task.duration_minutes,
                            "Priority": str(item.task.priority),
                            "Why": item.reason,
                        }
                        for item in plan.scheduled
                    ]
                )

            if plan.skipped:
                with st.expander(f"Left out of {plan.pet_name}'s day ({len(plan.skipped)})"):
                    for item in plan.skipped:
                        st.markdown(f"- **{item.task.title}** — {item.reason}")

            with st.expander(f"Explain {plan.pet_name}'s plan"):
                st.code(scheduler.explain(plan), language=None)

        if total_used < owner.minutes_available and total_skipped:
            st.caption(
                f"{owner.minutes_available - total_used} min are still free. The "
                "scheduler places tasks highest-priority-first and never splits "
                "one, so a leftover gap can be too short for anything remaining."
            )
