# Provenance of Academy agents with Flowcept — hands-on tutorial

Take the **stock [Academy](https://github.com/academy-agents/academy) examples**,
instrument each with **[Flowcept](https://github.com/ORNL/flowcept)** to capture
provenance (**zero changes to the agent logic**), and **inspect** what happened —
including **where things fail**.

The examples are laid out as **step-by-step exercises**: each ships as a stock
Academy program that runs but records nothing, and you turn provenance on one
**STEP** at a time by uncommenting a block and re-running.

**Terminal-only**: every analysis is text (summaries, lineage trees, ASCII
dashboards, a markdown provenance card) — no images, no GUI — so it runs unchanged
over SSH on an **Aurora** compute node. CPU-friendly; LLM via **Argo → OpenAI →
local CPU model** (no mock).

---

## Setup

**One conda env for all 8 exercises.** Example 07 runs real GFN2-xTB chemistry
(rdkit + ASE + xtb, conda-forge only), so the whole tutorial uses conda — no venv,
no per-exercise env.

```bash
cd flowcept-academy
bash setup/install.sh                 # builds the `flowcept-academy` conda env + deps + settings
conda activate flowcept-academy
```

All 01–08 run in this single env. **Example 07** additionally needs a tool-capable
LLM (its `tool_calling` node retries until it gets a parseable tool call); the
default local 0.5B model doesn't emit tool calls, so run 07 with Argo or OpenAI
(or a tool-capable local model — see its README):

```bash
cd exercises/local/07-mol-design
ARGO_USER=<your_anl_username> python solution.py
```

## The exercises

Everything hands-on lives under [`exercises/`](exercises/), the same eight
examples in two flavors:

```
exercises/
  local/    run on a laptop / login shell   (python exercise.py)
  aurora/   run on ALCF Aurora              (qsub submit.pbs; shared env.sh)
```

Each example folder has `agent_src.py` (the upstream Academy agent code, vendored
**unchanged**), `exercise.py` (uncomment-and-run STEP blocks), `solution.py` (every
step enabled), and a `README.md`.

```bash
cd exercises/local/01-actor-client
python exercise.py          # STEP 0: baseline (no provenance)
# uncomment STEP 1 in main(), re-run; then STEP 2, ... then STEP 5.
python solution.py          # or just run the fully-instrumented reference
```

| # | Example | Provenance it shows | Needs |
|---|---------|---------------------|-------|
| 01 | actor-client | agent lifecycle + actions | — |
| 02 | agent-loop | autonomous `@loop` events | — |
| 03 | agent-agent | cross-agent calls | — |
| 04 | execution | multi-process capture (`make_process_executor`) | — |
| 05 | parsl | agent delegating to a Parsl task | `parsl` |
| 06 | llm | LLM call + cross-agent tool call | LLM |
| 07 | mol-design | cross-framework (Academy `@loop` + LangGraph graph) driving **real GFN2-xTB** ionization-energy calculations | `langgraph`, `rdkit`+`ase`+`xtb` (conda), tool-capable LLM |
| 08 | discussion | multi-agent LLM group chat | LLM |

Example **07 is the real-chemistry example**: the upstream Academy `mol-design`
agent runs an LLM reasoning campaign (a LangGraph `StateGraph` inside an Academy
`@loop`) that proposes molecules and scores them with **actual GFN2-xTB**
relaxations (rdkit + ASE + xtb) — **nothing is mocked**. It runs in the same
`flowcept-academy` conda env as the rest; the only extra requirement is a
tool-capable LLM (its `tool_calling` node retries until it gets a parseable tool
call — Argo or OpenAI, or a tool-capable local model). See
[`exercises/local/07-mol-design/README.md`](exercises/local/07-mol-design/README.md).

## The steps (every example)

Work in `exercise.py`; uncomment one STEP block at a time and re-run:

| Step | Turn on | New output |
|------|---------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | `flowcept_buffer.jsonl` (offline: no Redis/Mongo) |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `<id>_card.md` (Flowcept's markdown card) |
| 5 | `provenance/query.py runs/<id>_*` | natural-language questions → pandas |

Every run writes its artifacts (`flowcept_buffer.jsonl`, perf CSV, `<id>_card.md`)
into a fresh `runs/<id>_<date-time>/` under the example folder, so repeated runs
never overwrite each other.

## The one line (what instrumentation looks like)

```python
from flowcept_academy.capture import captured

with captured(workflow_name="03-agent-agent"):
    result = asyncio.run(run())      # the stock example, now captured
```

## LLM backend: Argo → OpenAI → local CPU

Checked in priority order (first match wins):

| Condition | Backend |
|---|---|
| `ARGO_USER` set | ANL **Argo** gateway (Aurora / ANL network), native tool calling |
| else `OPENAI_API_KEY` set | **OpenAI** (`api.openai.com`, model `OPENAI_MODEL`, default `gpt-4o-mini`), native tool calling |
| else | **local CPU** model (`Qwen/Qwen2.5-0.5B-Instruct`, needs `transformers`+`torch`) |

The chain falls back automatically. There is **no mock backend** — every response
comes from a real model; if none is usable, `chat()` raises instead of fabricating
text. Force with `FLOWCEPT_TUTORIAL_LLM=argo|openai|local`; pick the local model
with `FLOWCEPT_TUTORIAL_MODEL=...`. Examples that need tool calls (e.g. 07) work on
Argo or OpenAI; the local 0.5B model does not emit tool calls.

---

## Inspect & query the provenance (terminal)

STEPs 2–4 print the analysis inline. To explore a captured buffer afterward:

```bash
cd exercises/local/06-llm && python solution.py    # writes runs/06-llm_<date-time>/
python ../../../provenance/analyze.py runs/06-llm_*   # summary, lineage, tailored, dashboard, card
python ../../../provenance/query.py runs/06-llm_*     # interactive: df, records, prov, ask("...")
```

`query.py` drops you into a shell with `df` (tasks), `records`, `prov`, `pd`, and
an `ask("...")` that answers **natural-language** questions by translating them to
pandas with the LLM:

```python
ask("which tasks failed and why?")
ask("how many LLM calls per agent and total tokens?")
df[df.subtype == "llm_call"][["used.call_type", "generated.total_tokens"]]   # or plain pandas
```

One-shot: `python ../../../provenance/query.py runs/06-llm_* --ask "which tasks failed?"`.
A ready-to-inspect sample ships in [`provenance/sample/`](provenance/sample/)
(a real example-07 run — cross-framework Academy + LangGraph + xTB), so you can try
analysis without running anything. Flowcept also ships its own NL provenance agent:
`flowcept --start-agent`.

## Inspecting failures

Whenever an agent action raises, Flowcept records that task with `status=ERROR` and
the `stderr`, and the analysis surfaces it — so you can see exactly which step
failed, on what input, and why (e.g. an LLM proposing a molecule whose SMILES xTB
can't parse shows up as a failed `compute_ionization_energy`):

```
⚠  Failures captured (status=ERROR) -- provenance records what broke:
    academy_action/<action> [ERROR] stderr: <the exception message>
```

---

## Layout

```
flowcept-academy/
├── exercises/
│   ├── local/<id>/     exercise.py (steps) · solution.py · README.md
│   └── aurora/<id>/    + submit.pbs        · env.sh (shared)
├── flowcept_academy/   # the reusable library
│   ├── capture.py      # captured() + langgraph_capture(): turn provenance on
│   ├── provenance.py   # load / summarize / lineage / tailored / card / text dashboard
│   └── util.py         # run() helper + make_chat_model()/chat() (Argo -> OpenAI -> local, no mock)
├── provenance/
│   ├── analyze.py      # inspect any buffer / dir (+ --all), terminal-only
│   ├── query.py        # interactive shell + ask("...") NL queries
│   └── sample/         # a ready-to-inspect captured run (real example 07)
├── slides/             # Beamer teaching deck
└── setup/              # offline settings + install.sh
```

## Slides & Aurora

- Slides: `cd slides && make` → `flowcept_academy.pdf`.
- Aurora: see [`exercises/aurora/README.md`](exercises/aurora/README.md) — offline
  local CPU model (or `ARGO_USER`), provenance offline, per-example `submit.pbs`.

Built for ATPESC. Flowcept (ORNL); Academy (Globus Labs / ANL). Example 07 runs
real GFN2-xTB chemistry (rdkit + ASE + xtb).
