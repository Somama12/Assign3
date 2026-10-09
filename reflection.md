# PawPal+ Project Reflection

## 1. System Design

### a. Initial design

My goal for PawPal+ was to support three main actions: add a pet, add care tasks
for that pet, and generate a daily schedule across all of the owner's pets.
The schedule needed to fit the owner's available time and explain which tasks
could not fit.

I organized the application around four classes:

- **Owner** stores the owner's name, available minutes, preferences, and pets.
- **Pet** stores identifying details and manages its collection of care tasks.
- **Task** stores a description, duration, priority, frequency, due date or preferred time, and completion status.
- **Scheduler** organizes tasks across pets, detects conflicts, and builds the daily plan.

This structure follows the relationship Owner → Pet → Task. I kept scheduling
rules in `pawpal_system.py`, separate from the Streamlit interface in `app.py`.
That allows the CLI, browser interface, and tests to use the same logic.
Dataclasses reduce repetitive setup code for the objects that mainly hold data.

### b. Design changes

The final design includes `ScheduledTask`, `SkippedTask`, `DailyPlan`, and
`Conflict`. Returning only a list of tasks would lose information about start
times and why a task was left out. These result classes make the schedule easier
to display and explain.

Another important design choice was to plan all pets against one shared timeline
and time budget. Planning each pet independently could schedule two activities at
the same time or let the first pet consume the entire budget. The final
`build_plans()` method considers the household together before grouping results
by pet.

For the extensions, I used Codex to add JSON persistence and a next-available-slot
feature. Save/load belongs on Owner because the owner contains the pets and their
tasks. Stable task IDs and follow-up IDs were also added so undoing a completion
removes the correct recurring task, including after saving and loading.

The final Mermaid source in `diagrams/uml_final.mmd` reflects these additions.

## 2. Scheduling Logic and Tradeoffs

### a. Constraints and priorities

The scheduler first selects pending tasks due on the planning date. Fixed-time
tasks reserve their requested times when they fit the day window and budget.
Flexible tasks are then considered by priority, owner preference, and duration.
All pets share the same busy intervals and available minutes.

Priority sorting and plan generation have slightly different responsibilities.
`sort_by_priority()` orders tasks by priority and then duration. The planner
also respects fixed appointments, so a fixed low-priority task can be placed
before a flexible high-priority task. I documented that behavior instead of
claiming priority always overrides every other constraint.

Conflict detection compares full time intervals. An 08:00–08:30 walk conflicts
with an 08:15–08:25 task even though their start times differ. Tasks that touch
at an endpoint, such as 08:00–08:30 and 08:30–08:40, do not conflict.

Daily completion queues an occurrence for the following day. Weekly completion
queues the next configured weekday. Repeating the completion operation does not
create another follow-up, and undo uses the follow-up's ID rather than its title.

### b. Tradeoffs

I kept the greedy scheduling approach because its decisions are understandable.
It takes a task when it fits and does not backtrack to search every possible
combination. This can leave unused time, and it does not guarantee the largest
number of completed tasks. The benefit is that each scheduled or skipped task
has a clear reason.

Conflict detection uses pairwise comparisons, which take O(n²) time. That is a
reasonable simplicity tradeoff for a household-sized list. Reporting all conflicts
can itself produce many pairs, so a larger application would need to consider
both search cost and the size of the results.

The next-slot feature reuses the generated plan. It respects the remaining budget,
existing activities, and the end of the day, but it only suggests a slot; it does
not reserve it or rearrange the plan to create more space.

JSON persistence is explicit: I need to save before closing and load the snapshot
in a new session. This keeps the storage layer small, but it does not support
multiple users editing the same file at once. The snapshot saves household data,
not UI filters or the scheduler's day-window settings.

## 3. AI Collaboration

### a. How I used AI

I supplied Codex with the assignment requirements, rubric, starter repository,
and my GitHub account. I asked it to complete the required work and bonus features,
starting with GitHub access. It located my existing `Assign3` fork and extended
that implementation instead of starting over.

Agent mode was useful for changes that crossed several files. Persistence required
backend serialization, CLI options, UI controls, tests, and documentation. The
next-slot feature also needed matching code, demonstrations, and UML updates.
Codex made those changes and ran the verification commands.

I used AI assistance for this reflection and the project documentation as well.
The implementation and test results described here are tied to the repository
and executed commands. I did not make manual code corrections during the final
extension session; Codex made the fixes described in `ai_interactions.md`.

### b. Suggestions accepted, rejected, or modified

I kept the version of next-slot scheduling that reuses `build_plans()` and
`_first_open_slot()`. The simpler candidate only scanned fixed tasks. In the
comparison, it suggested a slot even when the owner's time budget was exhausted,
and it overlooked a flexible task already placed in the schedule. Those failures
made it unsuitable for the final application.

I also kept the recurrence-ID change. Matching a follow-up by title and date is
ambiguous when two tasks have the same title, and recalculating its date during
undo can fail on a later day. An explicit link identifies the intended task.

The conflict captions were modified to use the actual generated plan. Assuming
the first task in a reported pair was always kept could display the wrong result
when equal-time tasks had different priorities.

These examples show why I would not judge an AI suggestion only by whether it
looks readable. It needs to agree with the application's constraints and pass
checks that could expose a wrong answer.

### c. AI strategy and separate sessions

The most useful features were multi-file editing, inspection of existing code,
and running Python and pytest to verify changes. The final extension work used
one continuous Codex chat. I did not use separate chats for each phase or compare
two different AI models, so I cannot claim benefits from doing so.

Instead, the prompt comparison evaluated two strategies in the same session:
a minimal implementation brief and a brief that explicitly listed constraints.
The agent created and executed both approaches. The constraint-focused approach
was more useful because it accounted for flexible tasks and the shared budget.
The experiment is reproducible with
`python -m experiments.compare_slot_strategies`.

For a future project, I would consider a separate review session to challenge the
initial assumptions. For this project, the tests and comparison cases provided
concrete checks while the continuous chat retained the implementation context.

## 4. Testing and Verification

### a. What was tested

The final suite has **108 passing tests**:

- **72 domain tests** in `tests/test_pawpal.py` cover completion, task and pet collections, sorting, filtering, recurrence, conflicts, budgets, and multi-pet planning.
- **15 UI tests** in `tests/test_app.py` exercise the Streamlit app, including adding data, preserving session state, deleting rows, completing tasks, sorting, and showing conflicts.
- **21 extension cases** in `tests/test_extensions.py` cover JSON restoration, invalid snapshots, recurrence identity, next-slot constraints, and updated UI behavior.

Codex ran `python -m pytest -q --cov=pawpal_system --cov-report=term-missing` in
the project environment. All tests passed, with **99% line coverage** of the
logic layer. The README includes the actual output.

Verification also included running the CLI save and load commands in separate
processes, comparing the README sample with actual demo output, checking that
methods listed in the final UML exist in the implementation, and running the
prompt-strategy comparison.

The strongest regression cases check situations where a plausible solution can
still be wrong: a full budget despite free clock time, two pets sharing the same
timeline, undoing a recurrence after reload, and a conflict whose higher-priority
task appears second in the reported pair.

### b. Confidence

My confidence level is **4 out of 5**. The tests provide evidence that the system
follows its documented rules, but line coverage does not prove every input or
real-world workflow is correct. The planner also depends on the user entering
reasonable task durations.

The remaining limitations include one-time events, timezone handling, overnight
schedules, and concurrent editing. A larger application would need additional
validation, storage design, and usability testing around those cases.

## 5. Reflection

### a. What went well

Separating the logic layer from the UI made the project easier to extend and
verify. The same classes support the demo, Streamlit interface, persistence, and
tests. Structured plan results also make it possible to explain why an activity
was scheduled or skipped instead of only displaying an unexplained list.

The project history contains separate commits for the UML skeleton, core logic,
UI integration, scheduling algorithms, tests, and documentation. The extensions
were committed separately as well, keeping the work organized by meaningful
changes rather than one final upload.

### b. What I would improve

I would first add a one-time frequency so appointments do not automatically create
another occurrence. Next, I would connect slot suggestions to an explicit action
for adding or rescheduling a task, while keeping fixed-time changes under the
owner's control. For a multi-user version, I would replace local snapshots with
storage designed for concurrent updates.

### c. Key takeaway

My main takeaway is that a clear specification needs executable examples. A
request like “find an available slot” sounds straightforward, but the comparison
showed that it must also define whose tasks count, how flexible activities are
handled, and whether free clock time still fits the owner's budget.

Working with an AI agent can speed up implementation, but the project still needs
clear responsibilities, documented tradeoffs, and evidence that the result works.
For PawPal+, the CLI examples and regression tests made those decisions concrete.
