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

I used an AI coding assistant across all six phases: brainstorming the class
breakdown, generating the skeleton from the UML, implementing the scheduler,
drafting tests, and debugging. The work split roughly into three kinds of ask.

*Generation from a spec I had already fixed.* "Turn this UML into dataclasses
with empty method stubs" and "write tests for these four scheduling rules" were
the highest-value prompts, because I had already decided what I wanted and the
answer was mechanical. This is where the assistant saved the most time.

*Review of something concrete.* Attaching `pawpal_system.py` and asking "what
relationships are missing, and where are the logic bottlenecks?" produced the
four changes in section 1b. Asking about a *specific file* worked; asking
open-ended questions like "is this good code?" produced generic advice I could
not act on.

*Verification by running things.* The most useful habit was not a prompt at
all. Three of the bugs in this project were invisible in the source and obvious
in the output — the `IntEnum` printing `2` instead of `medium`, the cat's nail
trim starving the dog's breakfast, and two pets booked at 08:00. Running
`main.py` and reading it found all three. Later I did the same for the UI with
Streamlit's `AppTest` harness, which is how I found that duplicate task titles
crashed the page. Code that has been read is not code that has been run.

**b. Judgment and verification**

The clearest case of not accepting a suggestion was rejecting my own cleverer
one. I wrote `find_conflicts()` first as a sweep line: sort the fixed-time
tasks by start, keep a list of still-active tasks, compare each new task only
against those. O(n log n), about 20 lines, and the kind of thing that looks
impressive. Then I rewrote it as six lines of `itertools.combinations` that
compares every pair, which is O(n²), and kept that version. `n` is the
fixed-time tasks due on one day — a couple of dozen at the very most — so the
faster algorithm was solving a problem this app does not have, and the pairwise
version reads as the definition of the thing ("every pair that overlaps")
rather than as an algorithm you have to trust.

Two smaller ones. In Phase 1 I was advised to add a `recurrence` field to
`Task`, and left it out, because no logic read it yet and an unused field in a
skeleton is a guess about the future; when Phase 2 actually specified
frequency, it went in with `is_due_on()` to consume it. And in Phase 3, the
obvious control for "task done" is `st.checkbox` — I used a button instead,
because Streamlit widget state sticks to its key, so after deleting a row the
shifted indices would make a checkbox inherit the deleted row's state and
complete the wrong task.

How I verified things rather than trusting them:

- **Tests as an equivalence proof.** The 44 tests passing unchanged across the
  sweep-to-`combinations` swap is what turned a risky rewrite into a
  readability decision.
- **Diffing documentation against reality.** The sample output in `README.md`
  is checked line by line against live `python main.py` output, so the README
  cannot quietly drift from the code.
- **Checking the diagram against the code.** I verified `uml_final.mmd` in both
  directions — every member in the diagram exists in `pawpal_system.py`, and
  every public member in the code appears in the diagram.
- **Coverage as a gap finder, not a score.** The 93%-to-100% pass was worth
  doing because of *what* was uncovered: `Owner.remove_pet()` had no test at
  all, and neither did the branch of `_pack()` that skips a task whose
  preferred time is already taken — a behavior I had claimed in a commit
  message.

**c. AI strategy**

*Which assistant features were most effective.* Multi-file agent edits, for
changes that genuinely span files — adding `due_date` touched the logic layer,
the CLI demo, the tests and the UI together, and doing that as one coherent
change avoided the half-migrated state you get from editing files one at a
time. Second, the ability to *run* code and read real output, which is what
actually caught the bugs. Third, targeted review of a named file. Least
effective: anything open-ended. "Suggest improvements" reliably produced a list
of plausible features that would have made the system worse, like caching the
schedule or adding a database.

*Separate chat sessions.* The assignment suggests a fresh session per phase. In
practice I ran the whole build as one continuous session, so I should be honest
about what that traded away rather than claim a benefit I did not get. What
continuity bought was real: at the end of Phase 1 I flagged "how to split the
time budget between pets" as an open question, and the first Phase 2 demo run
answered it; in Phase 5 I worked from the edge-case list I had written in
section 4b in Phase 2, which is how the duplicate-pet-name bug got found. A
fresh session would have needed all of that re-established, and would probably
have skipped it. What it cost is the outside view. A separate session would not
have known that I had already chosen a greedy scheduler, and might have
questioned it instead of building on it — the risk of one long session is that
early decisions stop being decisions and become the furniture. Where I did get
that effect, it came from changing *activity* rather than session: writing
tests, which forces you to state what the code should do, and reading terminal
output, which does not care what you intended.

*Being the lead architect.* The assistant was consistently better at producing
code than at deciding what the code should be. Every judgment that mattered in
this project was a scoping or values call, not a technical one: that priority
must be compared across pets rather than pet-by-pet, because "the dog got fed"
beats "more boxes ticked"; that a fixed-time task should be dropped with a
warning rather than silently moved, because insulin at 09:40 is not the same
event as insulin at 09:00; that a readable O(n²) beats a clever O(n log n) at
this scale. None of those are answerable from the code alone — they come from
knowing what the app is *for*. The failure mode I had to watch was accepting
something because it was well-formed. Fluent code is not correct code, and the
only reliable defence I found was to keep asking for the thing that cannot be
faked: run it, and look at what came out.

---

## 4. Testing and Verification

**a. What you tested**

84 tests across two files.

`tests/test_pawpal.py` (72 tests) covers the logic layer, grouped as: the two
required behaviors (`mark_complete()` flips status, adding a task grows the
count), the data model, sorting, filtering, recurrence, conflict detection,
scheduling rules, and edge cases. `tests/test_app.py` (12 tests) drives the
real Streamlit script through `AppTest`.

The tests I value most are the ones that pin down a bug I actually hit:

- `test_high_priority_task_beats_another_pets_low_priority_task` and
  `test_two_pets_tasks_never_overlap_on_the_clock` — the priority inversion and
  double-booking the Phase 2 CLI demo exposed.
- `test_tasks_sharing_a_title_do_not_break_the_page` and
  `test_toggling_done_after_a_delete_hits_the_right_task` — the two Phase 3 UI
  bugs. Neither was reachable from the logic layer, which is why the UI needed
  its own tests.
- `test_conflict_sweep_reports_every_overlapping_pair` — guards against the
  plausible-looking shortcut of comparing each task only to the next one after
  sorting, which misses non-adjacent overlaps.
- `test_two_pets_with_the_same_name_get_separate_plans` — this one *failed when
  I wrote it*. See below.

**b. Confidence**

Four out of five. The logic layer is at 100% line coverage and every scheduling
rule has at least one test.

The Phase 5 edge-case pass earned that confidence by finding a real bug, not by
confirming what I already believed. `Scheduler._pack()` built its plans
dictionary keyed by `pet.name`, so an owner with two pets both called "Mochi"
got their tasks merged into one `DailyPlan` — and `build_plans()` returned *the
same object twice*. It is now keyed by object identity. I had listed duplicate
pet names in this section as an edge case worth testing before I wrote the
test, so the value was in following through on my own list rather than in the
idea.

Where the honest doubt sits: line coverage is not behaviour coverage. Every
test here checks that the scheduler follows the rules I gave it, not that those
rules produce a day an owner would actually want. The greedy pass leaving 10
minutes idle while a 15 minute task goes undone passes the whole suite.

What I would test next, in order:

- Durations that are wrong in the real world. Conflict detection trusts
  `duration_minutes`, so a "30 minute" walk that really takes 45 silently
  stops overlapping the 08:45 task it collides with. This is the gap most
  likely to bite a real user.
- Tasks near midnight, and a `day_end` earlier in the day than a task's
  `preferred_time` plus its duration.
- Whether a second pass over `DailyPlan.skipped` could fill leftover gaps
  without breaking the priority guarantee.
- Two browser tabs editing the same session, which the current
  `st.session_state` design does not account for at all.

---

## 5. Reflection

**a. What went well**

The layering. `pawpal_system.py` imports no Streamlit, which sounds like a
detail and turned out to be the decision everything else rested on. It let me
build the scheduler CLI-first and see it working in a terminal before any UI
existed, drive the same logic from `main.py`, the app and 87 tests, and get to
100% line coverage of the logic without fighting a UI framework. When I later
found UI bugs, they were *only* UI bugs — the scheduling rules were never in
question, because they had never been entangled with the rendering.

The other thing I am satisfied with is that the app explains itself. Every
scheduled task carries the reason it got its slot and every dropped task
carries the reason it did not fit. That started as a README requirement and
ended up being the feature that made the system debuggable: the Phase 2
priority-inversion bug was obvious the moment the output said *why* the cat's
nail trim had been chosen.

**b. What you would improve**

Three things, in order.

1. **Add `Frequency.ONCE`.** Every task currently recurs, so a one-off vet
   visit has to be deleted after completion instead of simply being finished.
   This is the sharpest edge a real user would hit.
2. **Handle a clash by offering the next free slot.** Right now an overlapping
   fixed-time task is dropped with a warning. Better would be to keep the
   warning but offer "move Thyroid meds to 08:30?" as a one-click choice —
   still the owner's decision, but with the arithmetic done for them.
3. **Reconsider the greedy pass.** With 40 minutes free the scheduler takes a
   30-minute task and then rejects a 25-minute one, leaving 10 minutes idle. A
   second pass over `DailyPlan.skipped` looking for anything that fits the
   leftover gaps would waste less of the day without touching the priority
   guarantee.

Further out, the design assumes one owner and one device. `st.session_state`
means data lives and dies with a browser session, so nothing survives a
refresh, and there is no notion of two people sharing pet care.

**c. Key takeaway**

Design decisions are mostly about what to leave out, and running the code is
the only way to find out whether you left out the right things.

Both halves of that came from the same moment. My Phase 1 design was defensible
on paper — four classes, clean responsibilities, a scheduler that read the
owner's budget. It also contained a bug I could not see: planning pets one at a
time meant one pet's low-priority tasks could starve another pet's
high-priority ones. No amount of re-reading the class diagram would have
surfaced that. Nine lines of demo output did, immediately, because a scheduler
that feeds the cat's nail trim before the dog's breakfast is obviously wrong to
a human in a way it is not obvious in a UML box.

The corollary for working with AI is the same lesson from the other side. The
assistant was never short of things to add — a cache, a database, a
`recurrence` field three phases before anything read it. Saying no to most of
them, and yes to the small number that the scenario actually demanded, was the
part of this project that was genuinely mine.

---

## 6. October 9, 2026 extension audit — Codex-assisted addendum

**Attribution.** Sections 1–5 above were already present in the repository when
this session began and are preserved as the earlier reflection. Their test counts
and coverage statements describe that earlier work, not the current suite. This
addendum records observed changes without inventing new first-person student
experiences or claiming to have verified the earlier chat history.

**Design decisions.** The extension kept Owner → Pet → Task ownership and placed
JSON save/load on Owner so one snapshot captures the entire household. ISO strings
represent dates/times, and loading restores the concrete dataclass and enum types.
The next-slot feature reuses Scheduler's shared plan rather than independently
scheduling each pet. Stable task/follow-up IDs make undo reliable across saved
snapshots and distinguish tasks that happen to have the same title.

**Accepted and rejected approaches.** The agent accepted reusing the existing
planner and rejected the minimal slot scan after executing counterexamples: the
scan ignored flexible tasks and the owner's remaining budget. See the reproducible
comparison in `ai_interactions.md`. Explicit JSON snapshots were chosen over a
new database dependency because this remains a small local application.

**Correctness verification.** All 108 tests passed, including 21 new cases for
persistence, UI restoration, recurrence identity and slot constraints. Current
logic line coverage is 99%; this supersedes the earlier 100% claim for the smaller
implementation. The CLI save and load ran in separate Python processes, and the
README contains actual terminal output. UI tests also checked that equal-time
conflict captions reflect which task the planner really keeps.

**Tradeoffs.** Save/load is explicit, not automatic; users must save before closing.
One local snapshot is not multi-user storage. The next-slot suggestion includes
only the generated plan and does not reserve a new task or solve a global
optimization problem. Fixed-time tasks retain precedence over flexible tasks.
The original limitations around one-time events and local-only time handling remain.

**Student review still needed.** Confirm or revise the implementation decision in
the prompt comparison, and add any personal learning or manual corrections after
reviewing the code. The agent cannot truthfully supply those experiences for the
student. No new separate model/chat sessions were used for this extension audit.
