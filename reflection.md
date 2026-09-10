# PawPal+ Project Reflection

## 1. System Design

**Three core actions a user should be able to perform**

1. Add a pet, with its basic info (name, species, breed, age).
2. Add a care task for that pet, with how long it takes and how important it is.
3. Generate today's plan — an ordered, timed list of tasks that fits the time the
   owner actually has, plus an explanation of why it chose that plan.

**a. Initial design**

My first draft had four classes:

- **Owner** — the person using the app. Holds their name, the minutes they have
  available today, their preferences, and the list of pets they own. It is the
  source of truth for the constraints the scheduler has to respect.
- **Pet** — one animal. Holds identifying info and the list of care tasks that
  belong to it, and can filter down to the tasks still pending.
- **Task** — one unit of care (a walk, a feeding, meds). Holds a title, a
  duration in minutes, a priority, and whether it has been completed.
- **Scheduler** — the only class with real logic. It reads the owner's time
  budget and the pet's pending tasks, then decides what to do and in what order.

The split follows who owns which data: `Owner` and `Pet` are containers, `Task`
is a value, and `Scheduler` is the one place decisions get made. Keeping the
scheduling rules out of `Pet` means I can change how planning works without
touching the data model. `Task` and `Pet` are Python dataclasses since they are
mostly fields.

**b. Design changes**

I asked my AI assistant to review the skeleton for missing relationships and
logic bottlenecks. Four changes came out of that review:

1. **Added `ScheduledTask` and `DailyPlan`.** `build_plan()` originally returned
   a plain `list[Task]`, which loses two things the app needs: a task carries no
   start time, so the UI cannot show "08:00 — Morning walk", and the list says
   nothing about which tasks were *dropped*. That second one was the real
   problem — `explain_plan()` was being handed a list with no record of what was
   excluded, so it could never justify the exclusions. `ScheduledTask` pairs a
   task with a clock time; `DailyPlan` carries the scheduled items, the skipped
   tasks, and the minutes used.
2. **Replaced the free-form `priority: str` with a `Priority` IntEnum.** As a
   string, `"High"` vs `"high"` vs a typo would silently break sorting with no
   error. As an `IntEnum` the values sort directly, which also let me delete
   `Task.priority_rank()` — the enum already is the rank.
3. **Stopped duplicating `minutes_available` on `Scheduler`.** Both `Owner` and
   `Scheduler` stored the time budget, so the two copies could drift apart.
   `Scheduler` now takes only `day_start` and reads the budget from the `Owner`
   passed into `build_plan()`, leaving one source of truth.
4. **Added `build_plans(owner)` for the multi-pet case.** `Owner` holds a *list*
   of pets, but the scheduler could only plan one, so a two-pet owner had no
   supported path. `build_plans()` plans every pet against the single shared
   time budget.

One suggestion I did not take was adding a `recurrence` field to `Task` for
daily vs weekly tasks. It is a genuine feature, but nothing in the current
scheduling design reads it yet, and an unused field in a skeleton is
speculative complexity. I left it out until the scheduling logic exists to use
it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
