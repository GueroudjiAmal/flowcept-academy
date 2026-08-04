# Provenance analysis & inspection

Turn captured provenance into answers — for any run, and including failures.

## Interactive querying

```bash
python provenance/query.py exercises/local/06-llm/   # shell: df, records, prov, pd, ask("...")
python provenance/query.py <buffer> --ask "which tasks failed and why?"
```
(Run an exercise's `solution.py` first so its `flowcept_buffer.jsonl` exists.)
`ask()` turns natural language into pandas via the LLM (Argo → vLLM → OpenAI → local).
Flowcept's own
NL agent: `flowcept --start-agent`.

Everything here is **terminal-only** — text summaries, ASCII dashboards, a markdown
card — so it runs over SSH on an Aurora compute node. No images.

## Files
- `analyze.py` — CLI: analyze one buffer / run dir, or **every buffer in a dir**
  with `--all`.
- `query.py` — interactive shell + `ask("...")` natural-language queries.
- `sample/` — a ready-to-inspect captured run (**example 07**: cross-framework
  Academy+LangGraph **and** a captured failure): `07-mol-design.jsonl` + `_card.md`.

## Inspect

```bash
# analyze one captured buffer (summary, lineage, tailored analysis, text dashboard, md card)
python provenance/analyze.py provenance/sample/07-mol-design.jsonl

# a run you just produced (pass the exercise dir or its buffer)
python provenance/analyze.py exercises/local/06-llm/

# every buffer under a directory, separately
python provenance/analyze.py --all exercises/local/ --out per_example_out
```

## What you get (auto-adapts to each example)
- **Summary** — records by subtype / agent / status.
- **Lineage** — `campaign → agents → actions → llm_calls`.
- **Tailored analysis** — only what the example produced: actions/state, `@loop`
  events, cross-agent calls, cross-process lineage, LLM calls (prompt→response,
  tokens), LangGraph nodes (cross-framework), a conversation transcript — and
  **⚠ Failures** (any `status=ERROR` task, with `stderr`).
- **Text dashboard** — ASCII bars (the 2nd panel adapts: LLM tokens, else tasks-by-activity).
- **Flowcept provenance card** — `<id>_card.md` (markdown), via `Flowcept.generate_report`.

Generate the card for any buffer directly:

```python
from flowcept_academy import provenance as prov
prov.provenance_card("provenance/sample/07-mol-design.jsonl", out_dir=".")
```
