# AI Interactions Log

## Scope and attribution

This entry records the October 9, 2026 Codex session. The user supplied the
assignment, chose the required features plus bonuses, and authorized work in their
GitHub account. Their existing public fork, `Somama12/Assign3`, already contained
the core implementation, Streamlit app, UML, reflection, and 87 tests.

The existing code was preserved and extended. This log does not claim the current
agent authored the earlier commits, used another model, or observed manual student
corrections that did not occur. Personal conclusions require the student's review.

## Agent Workflow

**Task requested by the user:** Complete PawPal+ against the supplied requirements
and all bonus criteria, first establishing GitHub access.

**Work completed by Codex:**

1. Verified authentication as Somama12 and admin permission on the existing fork.
2. Read the assignment and inspected the existing classes, UI, tests and documentation.
3. Added `Scheduler.next_available_slot()` using every pet's generated plan, one
   shared time budget, contiguous free intervals and a fixed day window.
4. Added versioned JSON save/load, CLI `--save` / `--load`, and explicit UI snapshot buttons.
5. Fixed duplicate completion and made recurrence undo identify the exact follow-up
   by stable ID, so it still works after reload or on a different day.
6. Fixed conflict captions to use actual plan decisions, and rebuilt the scheduler
   after saving changed day-window settings.
7. Added 21 regression cases and ran all 108 tests successfully; logic line coverage
   was 99%. Executed the CLI save and load commands in separate processes.
8. Updated both Mermaid sources, README examples, and the reflection addendum.
9. Created and ran a two-strategy experiment for next-slot logic (below).

**Files modified/added:**

| File | Work |
|---|---|
| `pawpal_system.py` | JSON snapshot methods, recurrence IDs/guards, next-slot algorithm |
| `app.py` | Snapshot controls, slot suggestion, accurate conflict captions and day-window refresh |
| `main.py` | Household priority display, next-slot output, save/load command options |
| `tests/test_extensions.py` | 21 persistence, UI, recurrence and slot-finding regression cases |
| `experiments/compare_slot_strategies.py` | Executable comparison of two implementation briefs |
| `diagrams/uml.mmd`, `diagrams/uml_final.mmd` | New fields and methods |
| `.gitignore` | Exclude runtime snapshots |
| `README.md`, `reflection.md`, `ai_interactions.md` | Run instructions, actual evidence and attribution |

**Manual corrections:** No manual student code corrections were observed in this
session. The student completed GitHub browser authorization. The fixes listed
above were agent-made and verified with tests. The student should review the code
and personal reflection before submitting; no assignment was submitted by the agent.

## Prompt Comparison

This compares **two prompting strategies using the same Codex tool**, not two
models. These were agent-authored implementation briefs evaluated in this session,
not verbatim messages sent by the student to separate chat sessions. Both candidate
implementations and the counterexample runner are available in
`experiments/compare_slot_strategies.py`; the final method lives in `pawpal_system.py`.

| Dimension | A: Minimal implementation brief | B: Constraint-focused implementation brief |
|---|---|---|
| Model/tool | Codex coding agent in this session | Same Codex coding agent and Python/pytest execution |
| Prompt/task | “Find the first gap between fixed tasks for all pets.” | “Find the earliest contiguous slot after planning all pets. Respect flexible tasks, the shared remaining budget and day boundaries; return no slot when impossible, without mutating tasks.” |
| Useful output | A short sorted-interval scan, easy to follow; correctly finds 08:30 after a fixed 08:00–08:30 task | `next_available_slot()` reuses `build_plans()` and `_first_open_slot()`, so proposals agree with the existing plan |
| Problems observed | Proposes 08:30 even when all available care minutes are used; proposes 08:00 on top of a flexible task already planned there | Builds the plan again for each query; relies on the existing greedy policy, rather than exploring alternative globally optimal plans |
| Verification | Executed against a normal case, exhausted budget and flexible-task case; failed the latter two expected results | Passed all three comparison cases and dedicated tests for cross-pet tasks, touching boundaries, insufficient contiguous time and invalid durations |
| Implementation decision | Rejected as incomplete for the application's constraints | Adopted in the implementation because explicit constraints prevented plausible but unusable suggestions |
| Final student decision | Not asserted on the student's behalf | Pending student review: keep or change the agent's choice after examining the evidence |

Reproduce the observed output:

```bash
python -m experiments.compare_slot_strategies
```

```text
Case              | Minimal | Constrained | Expected
Fixed task        | 08:30   | 08:30       | 08:30
Budget exhausted  | 08:30   | none        | none
Flexible task     | 08:00   | 08:30       | 08:30
```

**Conclusion from the experiment:** Naming the constraints and verifying explicit
counterexamples produced a more useful implementation than a short happy-path
brief. Reusing the planner also avoided maintaining a second set of scheduling
rules. This is a small, reproducible strategy comparison, not a model benchmark.
