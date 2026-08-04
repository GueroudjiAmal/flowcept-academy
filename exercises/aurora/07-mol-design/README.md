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

## Requirements (07 is special)

07 uses the **same `flowcept-academy` conda env and the shared `../env.sh`** as
every other exercise (that env already includes the real xTB stack — rdkit + ase +
xtb). The one extra requirement is a **tool-capable LLM**: its `tool_calling` node
retries until it gets a parseable tool call, so set `ARGO_USER` (if the node can
reach the ANL gateway) or a tool-capable local model via `FLOWCEPT_TUTORIAL_MODEL`.
Build the shared env once on a login node:

```bash
bash setup/install.sh                                 # -> conda env `flowcept-academy`
```

Then edit `-A <project>` in `submit.pbs` and `qsub submit.pbs`.

## Steps (aurora)

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

On Aurora, submit the job (edit `-A <project>` first):

```bash
qsub submit.pbs         # runs solution.py on a compute node
```

07's `submit.pbs` sources the shared `../env.sh` (modules, the `flowcept-academy`
conda env with rdkit+ase+xtb, Flowcept offline settings, and the LLM backend), the
same as every other exercise. To work through the steps interactively, grab a node
and run `python exercise.py` after `source ../env.sh` (set `ARGO_USER` first).

`solution.py` has every step enabled -- peek if you get stuck.

## Query the captured provenance (natural language -> pandas)

```bash
python ../../../provenance/query.py runs/07-mol-design_* --ask "which molecules were simulated and what were their ionization energies?"
python ../../../provenance/query.py runs/07-mol-design_* --ask "show the langgraph_node rows"
python ../../../provenance/query.py runs/07-mol-design_* --ask "which tasks have status ERROR and what is the stderr?"
```

> Runs in the shared `flowcept-academy` conda env (which includes rdkit + ase + xtb).
