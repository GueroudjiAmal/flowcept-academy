# Exercise 04 -- 04-execution

**Shows:** multi-process execution (make_process_executor)

What it does: a `Distributor` agent runs **in this process** and its `compute`
`@action` offloads a batch of CPU tasks to a pool of **separate worker processes**
built with Flowcept's `make_process_executor`.

What the provenance reveals:
  - the `compute` `academy_action` (captured in-process) with its `used` (the
    batch of sizes) and `generated` -- and each result in `generated` records the
    `pid`/`host` it ran on, so you can see the work **really crossed the process
    boundary** (the worker pids differ from the main pid and from each other).
  - `make_process_executor` wires every worker for capture and shares the run's
    `campaign_id`/`workflow_id`, so everything stays in one graph.

> **Offline note.** Upstream Academy example 04 runs the *agents themselves* in a
> process pool over an HTTP exchange and relies on Flowcept's **message queue** to
> aggregate the per-worker records. This tutorial runs fully **offline** (no MQ),
> where worker-process records can't be flushed back -- so example 04 keeps the
> agent in-process and offloads the *compute* to the pool. Same capability
> (`make_process_executor`, real separate processes), captured reliably offline.
> See `agent_src.py` for the full rationale.

## Steps (local)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/04-execution_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/04-execution_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `04-execution_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/04-execution_*` | natural-language questions -> pandas |

```bash
python exercise.py      # or: python solution.py
```

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/04-execution_*   # interactive REPL
python ../../../provenance/query.py runs/04-execution_* --ask "what pid and host did each result run on?"
python ../../../provenance/query.py runs/04-execution_* --ask "how many distinct worker processes ran the compute work?"
python ../../../provenance/query.py runs/04-execution_* --ask "show the compute action's used and generated"
```
