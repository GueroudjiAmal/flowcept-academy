# Provenance of Academy agents with Flowcept — hands-on tutorial

Take the **stock [Academy](https://github.com/academy-agents/academy) examples**,
instrument each with **[Flowcept](https://github.com/ORNL/flowcept)** to capture
provenance (**zero changes to the agent logic**), and **inspect** what happened —
including **where things fail**.

The examples are laid out as **step-by-step exercises**: each ships as a stock
Academy program that runs but records nothing, and you turn provenance on one
**STEP** at a time by uncommenting a block and re-running.

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

For what each example does, **what its provenance reveals**, and questions to ask the
query tool — plus a step-by-step **Running on Aurora** flow — see
[`WALKTHROUGHS.md`](WALKTHROUGHS.md).

```bash
cd exercises/local/01-actor-client
python exercise.py          # STEP 0: baseline (no provenance)
# uncomment STEP 1 in main(), re-run; then STEP 2, ... then STEP 4 (STEP 5 is query.py).
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
call — Argo, vLLM, or OpenAI, or a tool-capable local model). See
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

## LLM backend: Argo → vLLM → OpenAI → local CPU

Checked in priority order (first match wins):

| Condition | Backend |
|---|---|
| `ARGO_USER` set | ANL **Argo** gateway (Aurora / ANL network), native tool calling |
| else `VLLM_BASE_URL` / `OPENAI_BASE_URL` set | **vLLM** server we run (model `VLLM_MODEL`); native tool calling when started with `--enable-auto-tool-choice`. On Aurora, `source ../vllm_serve.sh && vllm_start` sets this up |
| else `OPENAI_API_KEY` set | **OpenAI** (`api.openai.com`, model `OPENAI_MODEL`, default `gpt-4o-mini`), native tool calling |
| else | **local CPU** model (`Qwen/Qwen2.5-0.5B-Instruct`, needs `transformers`+`torch`) |

The chain falls back automatically, ending at the **local CPU** model — so with no
env set at all, `chat()` still answers (never a mock: there is **no mock backend**,
every response comes from a real model). `FLOWCEPT_TUTORIAL_LLM=argo|vllm|openai|local`
forces one, checked before the chain; forcing one whose config is missing (e.g. `vllm`
with no `VLLM_BASE_URL`) raises rather than fabricating text. Pick the local model
with `FLOWCEPT_TUTORIAL_MODEL=...`. Examples that need tool calls (e.g. 07) work on
Argo, vLLM, or OpenAI; the local 0.5B model does not emit tool calls.

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

## License

Released under the [MIT License](LICENSE). The upstream Academy examples remain
under their own license ([github.com/academy-agents/academy](https://github.com/academy-agents/academy)).
