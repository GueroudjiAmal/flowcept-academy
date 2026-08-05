# Exercise 07 -- 07-mol-design

**Shows:** cross-framework provenance (Academy `@loop` + LangGraph graph) driving
**real GFN2-xTB** chemistry.

What it does: the upstream Academy `mol-design` agent (`agent_src.py`, vendored
unchanged) runs an LLM reasoning campaign to find molecules with high ionization
energy. The campaign is a LangGraph `StateGraph` (plan -> tool_calling -> simulate
-> conclude -> critique -> update, looping) running inside an Academy `@loop`; the
`simulate` step calls `compute_ionization_energy`, which runs an **actual GFN2-xTB**
relaxation (rdkit builds the geometry, ASE + xtb compute charged - neutral energy).
**Nothing is mocked.**

What the provenance reveals (one graph, three layers, one `campaign_id`):
  - **Academy plugin**: agent lifecycle, the `conduct_simulation_campaign`
    `@loop`, each `compute_ionization_energy` action, and `report`.
  - **LangChain callback** (`langgraph_capture`): the reasoning graph
    (`langgraph_graph`), every node (`langgraph_node`), each `llm.ainvoke`
    (`llm_call`, model + tokens), and each `tool_call` -- nested under the Academy
    loop, zero edits to the agent.
  - **real xTB energies**: each `tool_call` output is a real ionization energy for a
    real LLM-proposed molecule; a molecule xTB can't parse is recorded with
    `status=ERROR` + `stderr` (a real captured failure).

> **Expect the first poll(s) to show "0 molecules".** This is a real, non-deterministic
> agentic campaign: the LLM sometimes proposes chemically-sensible but SMILES-invalid
> strings (e.g. `CF3C(N)=O`, where `CF3` is shorthand RDKit rejects). The upstream graph
> is *designed* to recover — its `conclude`/`critique`/`update` nodes feed the parse
> failures back to the model, which fixes the SMILES a round or two later. The harness
> therefore polls several times and stops as soon as real energies appear, so the run
> length varies from one launch to the next.

## Requirements (07 is special)

07 runs in the **same `flowcept-academy` conda env** as every other exercise (that
env already includes the real xTB stack — rdkit + ase + xtb). The one extra
requirement is a **tool-capable LLM**: its `tool_calling` node retries until it
gets a parseable tool call, and the default local 0.5B model does not emit tool
calls and will not terminate that node. Use Argo, vLLM, or OpenAI, or a tool-capable
local model via `FLOWCEPT_TUTORIAL_MODEL`.

```bash
# once, from the repo root (builds the shared env used by all 8 exercises):
bash setup/install.sh                                 # -> conda env `flowcept-academy`
conda activate flowcept-academy
# then, from this folder, with a tool-capable backend (e.g. Argo, vLLM, or OpenAI):
ARGO_USER=<your_anl_username> python solution.py
```

## Steps (local)

Work in `exercise.py`. Run it, then uncomment one **STEP** block at a time and
re-run -- the terminal output grows as you add capture, inspection, analysis,
and the provenance card.

Each run writes to its own `runs/07-mol-design_<date-time>/` (buffer, perf CSV, and the markdown card) so repeated runs never overwrite each other.

| Step | What you turn on | New output |
|------|------------------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `runs/07-mol-design_<date-time>/flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `07-mol-design_card.md` in the run dir (Flowcept's markdown card) |
| 5 | `query.py runs/07-mol-design_*` | natural-language questions -> pandas |

```bash
python exercise.py      # or: python solution.py
```

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/07-mol-design_*   # interactive REPL
python ../../../provenance/query.py runs/07-mol-design_* --ask "which molecules were simulated and what were their ionization energies?"
python ../../../provenance/query.py runs/07-mol-design_* --ask "show the langgraph_node rows"
python ../../../provenance/query.py runs/07-mol-design_* --ask "how many tokens did the llm_call rows use in total?"
python ../../../provenance/query.py runs/07-mol-design_* --ask "which tasks have status ERROR and what is the stderr?"
```

> Runs in the shared `flowcept-academy` conda env (which includes rdkit + ase + xtb).

## Why it matters (the value of provenance)

`provenance_value.py` is a runnable answer to *"what did capturing all this buy
me?"* It takes a buffer (a run of yours, or the shipped sample) and asks six
questions the campaign's normal output **cannot** answer -- printing, for each, the
plain-English question, the exact pandas, the answer, and what you'd be blind to
without provenance:

1. **Cross-framework lineage** -- Academy `@loop` + LangGraph nodes + LLM/tool calls
   as ONE graph under a single `campaign_id` (three libraries, zero glue).
2. **The hidden failure rate** -- the invalid SMILES the LLM invented (in the sample,
   8 of 10 tool calls) that the ranked-list output silently drops.
3. **Black box vs. reality** -- molecules *attempted* vs. what the report surfaced.
4. **The reasoning trace** -- the propose → fail → recover sequence, in time order.
5. **Fully-attributed results** -- each real xTB energy tied to the model + campaign.
6. **Cost & compute accounting** -- LLM tokens per usable result, xTB wall-clock on
   real relaxations vs. wasted on parse failures.

```bash
python provenance_value.py                     # the shipped sample (always works)
python provenance_value.py runs/07-mol-design_*   # your own run
```

It is plain pandas (no LLM needed), so it runs anywhere the buffer does. The
`(natural language: ...)` line under each question is the same query you can hand to
`query.py --ask "..."`.
