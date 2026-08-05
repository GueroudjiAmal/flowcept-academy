# Exercise 03 -- 03-agent-agent

**Shows:** cross-agent calls

What it does: a `Coordinator` delegates to two worker agents -- `Lowerer` then
`Reverser` -- to transform "DEADBEEF" -> "deadbeef" -> "feebdaed".

What the provenance reveals:
  - the data-flow chain across agents via each action's `used`/`generated`.
  - **cross-agent edges**: the `lower`/`reverse` action records carry
    `custom_metadata.cross_agent_call = true` and `source_agent_id` (the
    Coordinator) -- so "who called whom" is reconstructable (the agent-to-agent
    graph), not just what each agent did in isolation.
  - one sub-workflow per agent under the shared campaign.

## Steps (aurora)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/03-agent-agent_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/03-agent-agent_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `03-agent-agent_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/03-agent-agent_*` | natural-language questions -> pandas |

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
python ../../../provenance/query.py runs/03-agent-agent_* --ask "show the cross-agent calls"
```
