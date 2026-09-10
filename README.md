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

`python main.py` runs four sections. Jordan has 90 minutes, two pets and nine
tasks between them, so the scheduler has to leave some out.

**1. The daily plan**

```
==============================================================
        TODAY'S SCHEDULE - Monday, September 14, 2026         
==============================================================
Owner:      Jordan
Time today: 90 min
Prefers:    walk, play
Pets:       Mochi (dog, Shiba Inu, 3y), Pickle (cat, Tabby, 7y)
Conflicts:  none detected

--------------------------------------------------------------
MOCHI
--------------------------------------------------------------
  08:00-08:30  Morning walk     30 min
               high     why: fixed 08:00 slot you asked for
  08:30-08:40  Breakfast        10 min
               high     why: high priority
  18:00-18:25  Evening walk     25 min
               medium   why: fixed 18:00 slot you asked for

  3 tasks, 65 min of care

  Left out:
    - Brush coat      needs 20 min, only 10 min left of your 90
    - Puzzle feeder   needs 15 min, only 10 min left of your 90

--------------------------------------------------------------
PICKLE
--------------------------------------------------------------
  08:40-08:50  Wet food         10 min
               medium   why: medium priority
  09:00-09:05  Thyroid meds      5 min
               high     why: fixed 09:00 slot you asked for

  2 tasks, 15 min of care

  Left out:
    - Wand play       needs 15 min, only 10 min left of your 90
    - Clip nails      needs 25 min, only 10 min left of your 90

--------------------------------------------------------------
  5 tasks planned, 4 left out, 80/90 min used
```

Both pets are planned against **one** clock, so no two tasks overlap even
across pets. `Brush coat` is weekly and only appears because the demo day is a
Monday. 10 minutes go unused because nothing remaining is short enough to fit —
the scheduler never splits a task.

**2. Sorting and filtering**

```
==============================================================
                    SORTING AND FILTERING                     
==============================================================
Mochi's tasks in the order they were entered:
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    
    08:00  Morning walk     30 min  high   
      --    Breakfast        10 min  high   
      --    Brush coat       20 min  medium 

Scheduler.sort_by_time() - fixed times first, unpinned tasks last:
    08:00  Morning walk     30 min  high   
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    
      --    Breakfast        10 min  high   
      --    Brush coat       20 min  medium 

Scheduler.sort_by_priority() - highest priority, then shortest:
      --    Breakfast        10 min  high   
    08:00  Morning walk     30 min  high   
      --    Brush coat       20 min  medium 
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    

Owner.filter_tasks(pet_name='Pickle') - one pet only:
      --    Wand play        15 min  low    
    09:00  Thyroid meds      5 min  high   
      --    Clip nails       25 min  low    
      --    Wet food         10 min  medium 

Owner.filter_tasks(priority='high') - across every pet:
    08:00  Morning walk     30 min  high   
      --    Breakfast        10 min  high   
    09:00  Thyroid meds      5 min  high   

Owner.filter_tasks(completed=False, due_on=PLANNING_DAY) - due today:
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    
    08:00  Morning walk     30 min  high   
      --    Breakfast        10 min  high   
      --    Brush coat       20 min  medium 
      --    Wand play        15 min  low    
    09:00  Thyroid meds      5 min  high   
      --    Clip nails       25 min  low    
      --    Wet food         10 min  medium 
    ^ 'Brush coat' is weekly on Monday, so it appears here but would not
      on any other weekday.
```

**3. Recurring tasks**

```
==============================================================
                       RECURRING TASKS                        
==============================================================
Completed 'Breakfast' (daily) on Mon Sep 14
  -> queued: Breakfast (10 min, high, due Tue Sep 15)
Completed 'Brush coat' (weekly) on Mon Sep 14
  -> queued: Brush coat (20 min, medium, due Mon Sep 21)

Mochi's pending list now carries the next occurrences:
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    
    08:00  Morning walk     30 min  high   
      --    Breakfast        10 min  high     due Tue Sep 15
      --    Brush coat       20 min  medium   due Mon Sep 21

Still due on Mon Sep 14 (the follow-ups are not):
    18:00  Evening walk     25 min  medium 
      --    Puzzle feeder    15 min  low    
    08:00  Morning walk     30 min  high   
```

**4. Conflict detection**

```
==============================================================
                      CONFLICT DETECTION                      
==============================================================
Three tasks pinned to overlapping times:
    08:00-08:30  Morning walk    (Mochi)
    08:15-08:25  Insulin shot    (Pickle)
    08:20-08:25  Eye drops       (Pickle)

Scheduler.conflict_warnings() found 3:
    ! 'Morning walk' for Mochi (08:00-08:30) overlaps 'Insulin shot' for Pickle (08:15-08:25) - you cannot be in two places at once
    ! 'Morning walk' for Mochi (08:00-08:30) overlaps 'Eye drops' for Pickle (08:20-08:25) - you cannot be in two places at once
    ! Pickle: 'Insulin shot' (08:15-08:25) overlaps 'Eye drops' (08:20-08:25)

The plan still builds - the loser is skipped, not crashed on:
    kept    08:00  Morning walk (Mochi)
    skipped       Insulin shot (Pickle) - its preferred time overlaps an earlier task
    skipped       Eye drops (Pickle) - its preferred time overlaps an earlier task
```

Note the second warning: `Morning walk` clashes with **both** later tasks. A
naive "compare each task with the next one" check would report only the first
pair and miss `Morning walk` vs `Eye drops`.

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
collected 44 items
tests/test_pawpal.py ............................................        [100%]
============================== 44 passed in 0.03s ==============================
```

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sort by time | `Scheduler.sort_by_time()` | Fixed-time tasks in clock order, unpinned tasks last. Because `preferred_time` is a real `datetime.time`, the sort key is just the value itself — no `"HH:MM"` string parsing needed |
| Sort by priority | `Scheduler.sort_by_priority()` | Highest priority first, shortest duration breaking ties |
| Filter by pet | `Owner.filter_tasks(pet_name=...)` | Delegates to each `Pet.filter_tasks()` |
| Filter by status | `Pet.filter_tasks(completed=...)` | Also filters by `priority`, `frequency` and `due_on`; every supplied criterion must match |
| Recurring tasks | `Pet.complete_task()`, `Task.next_occurrence()`, `Task.next_due_date()` | Completing a task queues its next instance — `timedelta(days=1)` for daily, the next matching weekday for weekly. `Pet.uncomplete_task()` removes the follow-up if you undo |
| Due dates | `Task.due_date`, `Task.is_due_on()` | A queued follow-up stays out of today's plan; an **overdue** task stays due rather than vanishing |
| Conflict detection | `Scheduler.find_conflicts()`, `Scheduler.conflict_warnings()` | Reports every overlapping pair of fixed-time tasks, within a pet and across pets. Returns warning strings — it never raises |
| Conflict resolution | `Scheduler._pack()` | One shared timeline for all pets, so nothing overlaps; a fixed-time task landing on a taken slot is skipped with a reason |
| Time budget | `Owner.minutes_available`, `DailyPlan.minutes_used` | One shared pool across all pets; anything that doesn't fit lands in `DailyPlan.skipped` with a reason |
| Explanation | `Scheduler.explain()`, `ScheduledTask.reason` | Every scheduled and skipped task carries the reason it got that treatment |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
