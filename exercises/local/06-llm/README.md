# Exercise 06 -- 06-llm

**Shows:** LLM call + cross-agent tool call

What it does: an `Orchestrator` builds a LangChain ReACT agent (`create_agent`)
over a tool that messages a separate `MySimAgent`; the LLM decides whether to call
the tool for a simulated energy, then writes the answer. (LLM = Argo → vLLM →
OpenAI → local CPU model, in priority order.)

What the provenance reveals:
  - `llm_call` tasks linked to their enclosing `@action` (`answer`) via
    `parent_task_id`, with the model used and **token counts**.
  - the ReACT graph as `langgraph_graph` + `langgraph_node` records captured by the
    LangChain callback (`langgraph_capture`), sharing the campaign.
  - when the LLM calls the tool, a **cross-agent tool call** (Orchestrator ->
    `MySimAgent.compute_ionization_energy`) tying the reasoning to the tool result.
    (A small local model may answer directly; a tool-capable backend exercises the
    full path.)

## Steps (local)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/06-llm_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/06-llm_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `06-llm_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/06-llm_*` | natural-language questions -> pandas |

```bash
python exercise.py      # or: python solution.py
```

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/06-llm_*   # interactive REPL
python ../../../provenance/query.py runs/06-llm_* --ask "how many llm_call rows are there and total tokens?"
python ../../../provenance/query.py runs/06-llm_* --ask "show used.user_prompt and generated.response_text for each llm_call"
python ../../../provenance/query.py runs/06-llm_* --ask "show the cross-agent calls"
```
