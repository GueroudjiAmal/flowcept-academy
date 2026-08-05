# Exercise 05 -- 05-parsl

**Shows:** agent delegating to a Parsl task

What it does: a `SimulationAgent` delegates a compute task to **Parsl** (a
`@python_app`) and awaits its result.

What the provenance reveals:
  - the dispatching `academy_action` (`run_expensive_task`) with its `generated`
    result (42) -- the agent -> Parsl hand-off is captured.
  - the pattern that scales in example 07: there, the agent's process pool runs real xTB chemistry
    across workers, and each worker task also emits a `tool_call` linked back to
    the action (same `parent_task_id` idea as example 04).

## Steps (aurora)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/05-parsl_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/05-parsl_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `05-parsl_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/05-parsl_*` | natural-language questions -> pandas |

On Aurora, submit the job (`submit.pbs` already has `-A ATPESC2026`):

```bash
qsub submit.pbs         # runs solution.py on a compute node
```

`submit.pbs` sources `../env.sh` (modules, conda env, offline local LLM, Flowcept
offline settings). To work through the steps interactively, grab a node and run
`python exercise.py` after `source ../env.sh`.

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/05-parsl_* --ask "what did run_expensive_task generate?"
```

> Requires the `parsl` extra (`pip install -e ".[parsl]"`).
