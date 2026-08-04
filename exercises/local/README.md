# Local exercises

Run these on your laptop or any login shell — no scheduler, no Aurora.

```bash
# once, from the repo root:
bash setup/install.sh
conda activate flowcept-academy

# then, per example:
cd exercises/local/01-actor-client
python exercise.py       # STEP 0 (baseline). Uncomment STEP 1, re-run, ...
python solution.py       # the fully instrumented reference
```

Each example folder has `exercise.py` (uncomment-and-run steps), `solution.py`
(every step enabled), and a `README.md` (the steps + what the provenance
reveals). See the [exercises overview](../README.md) for the list and the
common step sequence.

Examples 06–08 need an LLM. Backend is chosen in priority order: `ARGO_USER` →
Argo, else `OPENAI_API_KEY` → OpenAI, else a local CPU model — the first local
run downloads ~1 GB (`Qwen/Qwen2.5-0.5B-Instruct`) and generation is a few seconds. Examples 05 and 07 need extras (`parsl`, `langgraph`), installed by
`setup/install.sh`.
