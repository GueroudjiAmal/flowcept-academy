# Exercise 01 -- 01-actor-client

**Shows:** agent lifecycle + actions

What it does: launches one stateful `Counter` agent and, from a client, calls its
`@action`s (`increment`, `increment(10)`, `get_count`). No LLM, no other agents.

What the provenance reveals:
  - agent lifecycle: `academy_lifecycle` startup/shutdown records for the agent.
  - one `academy_action` per call, each with `used` (inputs) and `generated`
    (outputs) -- so you can watch the state evolve: increment -> increment(10)
    -> get_count = 11, every call marked status=FINISHED.
  - the simplest possible capture: this is the baseline the other examples build on.

## Steps (local)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/01-actor-client_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/01-actor-client_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `01-actor-client_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/01-actor-client_*` | natural-language questions -> pandas |

```bash
python exercise.py      # or: python solution.py
```

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/01-actor-client_*   # interactive REPL
python ../../../provenance/query.py runs/01-actor-client_* --ask "how many actions did the agent run?"
python ../../../provenance/query.py runs/01-actor-client_* --ask "what value did each increment produce?"
python ../../../provenance/query.py runs/01-actor-client_* --ask "show the academy_lifecycle events"
```
