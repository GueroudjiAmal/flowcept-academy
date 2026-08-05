# Exercise 02 -- 02-agent-loop

**Shows:** autonomous @loop events

What it does: a `Counter` agent with an autonomous `@loop` (`ticker`) that
increments itself every 0.5s in the background; the client just reads the count.

What the provenance reveals:
  - `academy_loop` records for the loop's **start** and **exit**, sharing a
    `group_id` -- so autonomous behavior is captured distinctly from
    request/response actions.
  - you can see the loop actually ran and when it stopped (at agent shutdown),
    even though nobody "called" it -- provenance captures proactive behavior, not
    just reactive calls.

## Steps (aurora)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/02-agent-loop_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/02-agent-loop_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `02-agent-loop_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/02-agent-loop_*` | natural-language questions -> pandas |

On Aurora, submit the job (`submit.pbs` already has `-A ATPESC`):

```bash
qsub submit.pbs         # runs solution.py on a compute node
```

`submit.pbs` sources `../env.sh` (modules, conda env, offline local LLM, Flowcept
offline settings). To work through the steps interactively, grab a node and run
`python exercise.py` after `source ../env.sh`.

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/02-agent-loop_* --ask "how many academy_loop events were captured?"
```
