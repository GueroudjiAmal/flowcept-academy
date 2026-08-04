# Exercise 08 -- 08-discussion

**Shows:** multi-agent LLM group chat

What it does: a round-robin **LLM group chat** (upstream `group_chat_agents.py`,
vendored unchanged) -- three role-playing `GroupChatAgent`s (Manager, Assistant,
Senior Engineer) take turns via `respond`/`receive`, coordinated by a
`RoundRobinGroupChatManager` that also runs a supervisor `@loop` watching for the
conversation getting stuck. Bounded by `max_rounds` (harness knob).

What the provenance reveals:
  - one `llm_call` per turn (each participant's `respond`, plus the manager's
    stopping / supervisor checks) with the model and **tokens per agent**.
  - the `receive` actions capture the **message fan-out** between agents (each agent
    broadcasts to its peers and the manager), so the dialogue structure is queryable.
  - the supervisor `@loop` (`academy_loop`) shows the manager's autonomous
    monitoring running alongside the turn-taking.

## Steps (local)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/08-discussion_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/08-discussion_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `08-discussion_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/08-discussion_*` | natural-language questions -> pandas |

```bash
python exercise.py      # or: python solution.py
```

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/08-discussion_*   # interactive REPL
python ../../../provenance/query.py runs/08-discussion_* --ask "total tokens per agent for llm_call rows"
python ../../../provenance/query.py runs/08-discussion_* --ask "show generated.response_text for each llm_call"
python ../../../provenance/query.py runs/08-discussion_* --ask "how many actions are receive versus respond?"
```
