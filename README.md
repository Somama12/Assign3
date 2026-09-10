# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Output of `python main.py` — Jordan has 90 minutes, two pets, and eight tasks
between them, so the scheduler has to leave some out:

```
==============================================================
        TODAY'S SCHEDULE - Monday, September 14, 2026
==============================================================
Owner:      Jordan
Time today: 90 min
Prefers:    walk, play
Pets:       Mochi (dog, Shiba Inu, 3y), Pickle (cat, Tabby, 7y)

--------------------------------------------------------------
MOCHI
--------------------------------------------------------------
  08:00-08:30  Morning walk     30 min
               high     why: fixed 08:00 slot you asked for
  08:30-08:40  Breakfast        10 min
               high     why: high priority
  09:05-09:25  Brush coat       20 min
               medium   why: medium priority

  3 tasks, 60 min of care

  Left out:
    - Puzzle feeder   your 90 min for the day was already full

--------------------------------------------------------------
PICKLE
--------------------------------------------------------------
  08:40-08:50  Wet food         10 min
               medium   why: medium priority
  09:00-09:05  Thyroid meds      5 min
               high     why: fixed 09:00 slot you asked for
  09:25-09:40  Wand play        15 min
               low      why: low priority, and matches your preferences

  3 tasks, 30 min of care

  Left out:
    - Clip nails      your 90 min for the day was already full

==============================================================
  6 tasks planned, 2 left out, 90/90 min used
==============================================================
```

Things to notice: both pets are planned against **one** clock, so no two tasks
overlap even across pets; `Brush coat` is weekly and only appears because the
demo day is a Monday; `Wand play` beat `Clip nails` at equal priority because
Jordan's preferences mention "play".

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-8.4.2, pluggy-1.5.0
rootdir: /Users/somamasiddiqui/Desktop/codepathAI/Assign3
configfile: pytest.ini
testpaths: tests
collected 21 items

tests/test_pawpal.py .....................                               [100%]

============================== 21 passed in 0.02s ==============================
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler._pack` | Fixed-time tasks placed first, then the rest by priority desc, owner preference, then shortest duration |
| Filtering | `Pet.tasks_due_on`, `Task.is_due_on` | Only pending tasks due on the planning day are candidates |
| Conflict handling | `Scheduler._first_open_slot` | One shared timeline for all pets, so nothing overlaps; a fixed-time task landing on a taken slot is skipped with a reason |
| Recurring tasks | `Task.frequency`, `Task.weekly_day` | `daily` is always due; `weekly` is due only on its weekday |
| Time budget | `Owner.minutes_available`, `DailyPlan.minutes_used` | One shared pool across all pets; anything that doesn't fit lands in `DailyPlan.skipped` with a reason |
| Explanation | `Scheduler.explain`, `ScheduledTask.reason` | Every scheduled and skipped task carries the reason it got that treatment |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
