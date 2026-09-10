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

One suggestion I did not take at the skeleton stage was adding a `recurrence`
field to `Task` for daily vs weekly tasks. It is a genuine feature, but nothing
in the skeleton read it yet, and an unused field is speculative complexity.
Phase 2 then specified frequency as part of `Task`, so it went in as a
`Frequency` enum plus a `weekly_day` — at that point there was real logic
(`Task.is_due_on`) to consume it.

Three more changes came out of actually running the code, not from reading it:

5. **The `Priority` IntEnum printed as a number.** `Task.__str__` used an
   f-string, and f-strings call `__format__`, which `IntEnum` inherits from
   `int` — so my `__str__` was ignored and the demo printed
   "Morning walk (30 min, 2)". Overriding `Priority.__format__` fixed every
   call site at once. This is the change I would not have found by inspection;
   I only saw it because the CLI output looked wrong.
6. **Planning pet-by-pet inverted priority across pets.** `build_plans()`
   originally looped over pets, each drawing from the remaining budget. The
   first demo run scheduled Pickle's *nail clipping* (low) and left Mochi's
   *breakfast* (high) unfed, because the first pet's low-priority tasks
   consumed the budget before the second pet's high-priority tasks were even
   considered. In Phase 1 I had flagged budget-splitting as an open question;
   the demo answered it.
7. **Per-pet plans overlapped on the wall clock.** Each pet got its own busy
   list, so Mochi's 08:00-08:30 walk and Pickle's 08:00-08:10 feeding were both
   "scheduled" at 08:00. Jordan has one pair of hands.

Changes 6 and 7 share one fix: `Scheduler._pack()` now packs *all* pets'
candidate tasks against a single shared timeline and a single shared budget,
then groups the results into one `DailyPlan` per pet. Priority is therefore
compared across the whole household. I also added `SkippedTask` so each
dropped task carries the reason it was dropped, which is what makes
`explain()` able to justify itself.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler weighs five constraints:

1. **Due today** (`Task.is_due_on`) — daily tasks always count; weekly tasks
   only on their weekday. Completed tasks drop out entirely.
2. **Fixed times** (`Task.preferred_time`) — medication at 09:00 cannot float.
3. **Priority** (`Priority`) — the main ordering signal for everything else.
4. **Total time available** (`Owner.minutes_available`) — one shared pool for
   the whole household.
5. **Owner preferences** (`Owner.preferences`) — a keyword match against the
   task title.

I ranked them by what breaks if they are violated. Getting a fixed-time task
wrong can mean a missed dose, so those are placed first and never moved.
Priority comes next because it is the owner's own statement of what matters.
Preferences rank last: they only break ties between tasks of equal priority,
because a preference for walks should not outrank the cat's thyroid meds.
Duration is a tiebreak below that — among otherwise equal tasks the shorter one
goes first, which gets more tasks done inside the same budget.

**b. Tradeoffs**

The scheduler is **greedy, not optimal**. It walks the sorted task list once
and takes the first slot that fits, and it never backtracks. So a 30 minute
high-priority task will be scheduled even when two 15 minute medium tasks in
that slot would have completed more of the list, and with 40 minutes free it
will take a 30 minute task and then reject a 25 minute one, leaving 10 minutes
idle. A packing algorithm would fill the day more tightly.

That is the right tradeoff here. Optimal packing would sometimes drop a
high-priority task in order to fit more low-priority ones — which is exactly
backwards for pet care, where "the dog got walked" beats "more boxes ticked".
The greedy pass is also explainable: every task carries one sentence saying
why it landed where it did, and "highest priority first, then earliest open
slot" is a rule an owner can predict. An optimizer's output is much harder to
justify, and the README asks the app to explain its reasoning.

A second, smaller tradeoff: pets share one timeline, so tasks that could
genuinely happen at once (feeding two pets in the same kitchen) are serialized.
That is pessimistic, but it is the safe direction to be wrong in — it never
promises the owner they can be in two places at once.

**Tradeoffs in the Phase 4 algorithms**

*Conflict detection compares full time windows, not just start times.* The
cheap version of this check is `task_a.preferred_time == task_b.preferred_time`,
which is one line and catches the obvious case. I compare
`[start, start + duration)` intervals instead, because the case that actually
hurts an owner is the near miss: an 08:00 walk lasting 30 minutes and an 08:15
insulin shot do not share a start time, but they cannot both happen. Exact
matching would have called that pair fine. The cost is that "conflict" now
depends on durations being roughly honest — if the owner guesses 30 minutes for
a walk that really takes 45, the check silently misses the clash.

*Conflict detection is O(n²), deliberately.* I first wrote `find_conflicts()`
as a sweep line — sort by start time, keep a list of still-active tasks, compare
each new task only against those. That is O(n log n) and about 20 lines. I then
rewrote it with `itertools.combinations` in six lines, which compares all pairs
and is O(n²). I kept the slower one. `n` here is *fixed-time tasks due on a
single day*, which is a couple of dozen at the very most, so n² is on the order
of a few hundred comparisons — genuinely free — and the pairwise version reads
as the definition of the problem ("every pair that overlaps") instead of as an
algorithm you have to trust. The tests passed unchanged across the swap, which
is what let me treat it as a pure readability decision rather than a gamble. If
PawPal+ ever plans a shelter, the sweep is the right call and the docstring
says so.

*Overlapping fixed-time tasks are dropped, not moved.* When two tasks both want
09:00, `_pack()` keeps the first and skips the second with a reason. Sliding the
loser to the next free slot would get more done, but a task is pinned to a time
precisely because it cannot move — insulin at 09:00 is not the same event as
insulin at 09:40. Dropping it with a visible warning puts the decision back on
the owner, which is the honest outcome for the one class of task where guessing
wrong actually matters.

*Every task recurs.* There is no one-off frequency, so completing anything
queues another instance. That fits the scenario (feeding, walks and meds all
repeat) and keeps the model small, but it means a genuinely one-time task — a
vet visit — has to be deleted after completion rather than simply finished. A
`Frequency.ONCE` member would fix it and is the first thing I would add.

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

21 tests in `tests/test_pawpal.py`, in four groups:

- **The two required behaviors** — `mark_complete()` flips a task's status, and
  adding a task grows the pet's task count.
- **The data model** — completed tasks leave `pending_tasks()`, `remove_task()`
  reports whether it removed anything, a zero-duration task is rejected, and
  priority strings from the UI parse into the enum.
- **Recurrence** — a weekly task is due on its weekday and not on others.
- **Scheduling** — priority ordering, the time budget, fixed-time anchors,
  gap-filling ahead of an anchor, an anchor outside the day window, completed
  tasks not being rescheduled, and preferences breaking a tie.

The multi-pet tests matter most, because each one pins down a bug the demo
actually exposed: `test_high_priority_task_beats_another_pets_low_priority_task`
covers the priority inversion, `test_two_pets_tasks_never_overlap_on_the_clock`
covers the double-booking, and `test_shared_budget_is_not_spent_twice` covers
the budget. Those three would have caught all of it before I ran anything.

**b. Confidence**

Reasonably confident about the rules I wrote, and less so about the ones I have
not thought of. The tests cover each scheduling rule at least once, and the CLI
demo exercises them together on a realistic eight-task day. Two of the three
bugs I found in Phase 2 came from *running* the code rather than reading it,
which is a fair warning that a passing suite is not proof.

Edge cases I would test next:

- Two fixed-time tasks that want overlapping slots — the second is skipped, but
  I would rather it slide to the next free slot than be dropped.
- A task longer than the whole day window, or longer than the owner's budget.
- A day with zero minutes available, and an owner with no pets.
- Two pets with identical names, which `get_pet()` and the plan-grouping dict
  would currently conflate.
- Whether the greedy 10-minutes-idle case above is ever bad enough to be worth
  a second pass over the skipped list.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
