# Exercises — capturing provenance of Academy agents with Flowcept

Eight stock [Academy](https://github.com/academy-agents/academy) examples, each
turned into a **step-by-step provenance exercise**. As shipped, every example
runs but records *nothing*. You turn provenance on one **STEP** at a time by
uncommenting a block in `exercise.py` and re-running — the terminal report grows
as you add capture → inspection → analysis → a provenance card → interactive
queries.

```
exercises/
  local/    run on your laptop / a login shell   (python exercise.py)
  aurora/   run on ALCF Aurora                    (qsub submit.pbs)
    env.sh  modules + conda env + offline LLM + Flowcept settings
```

Same eight examples in both; `aurora/` adds a per-example `submit.pbs` and a
shared `env.sh`.

## The examples

| # | Example | Shows | Needs |
|---|---------|-------|-------|
| 01 | actor-client | agent lifecycle + actions | — |
| 02 | agent-loop | autonomous `@loop` events | — |
| 03 | agent-agent | cross-agent calls | — |
| 04 | execution | multi-process capture (`make_process_executor`) | — |
| 05 | parsl | agent delegating to a Parsl task | `parsl` |
| 06 | llm | LLM call + cross-agent tool call | LLM |
| 07 | mol-design | cross-framework provenance (Academy + LangGraph) | `langgraph`, LLM |
| 08 | discussion | multi-agent LLM group chat | LLM |

Examples 06–08 call a real LLM, chosen in priority order: **Argo** if `ARGO_USER`
is set, else a **vLLM** server if `VLLM_BASE_URL`/`OPENAI_BASE_URL` is set (the Aurora
path — a model served on the node's own GPUs), else **OpenAI** if `OPENAI_API_KEY` is
set, else a **local CPU model** (Hugging Face, offline). `FLOWCEPT_TUTORIAL_LLM` forces
one of these. There is no mock — see the repo [README](../README.md).

## The steps (same in every example)

Work in `exercise.py`. Run it, then uncomment one STEP block at a time:

| Step | Turn on | New output |
|------|---------|-----------|
| 0 | baseline run | just the result |
| 1 | `captured(...)` | a fresh `runs/<id>_<date-time>/` with `flowcept_buffer.jsonl` |
| 2 | `print_summary` + `print_lineage` | record counts + lineage tree |
| 3 | `print_tailored` + `text_dashboard` | content-aware report + ASCII dashboard |
| 4 | `provenance_card(...)` | `<id>_card.md` (Flowcept's markdown card) in the run dir |
| 5 | `provenance/query.py runs/<id>_*` | ask questions in natural language → pandas |

Every run writes to its own `runs/<id>_<date-time>/` under the example folder
(buffer, perf CSV, card, plus any framework logs), so repeated runs never
overwrite each other. `solution.py` in each folder has every step already
enabled — peek if stuck.

## Setup

Once, from the repo root:

```bash
bash setup/install.sh        # builds the `flowcept-academy` conda env, installs everything
conda activate flowcept-academy
```

Then:

```bash
cd exercises/local/01-actor-client
python exercise.py           # STEP 0, then uncomment STEP 1, re-run, ...
# each capturing run appears under ./runs/01-actor-client_<date-time>/
```

On Aurora, see [aurora/README.md](aurora/README.md).
