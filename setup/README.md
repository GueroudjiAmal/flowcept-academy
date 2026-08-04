# Setup

**One conda env for the whole tutorial** (all 8 exercises). Example 07 needs real
GFN2-xTB chemistry (`rdkit` + `xtb-python`, conda-forge only), so everything uses
conda — no venv, no per-exercise env.

```bash
bash setup/install.sh            # builds the `flowcept-academy` conda env + deps + settings
conda activate flowcept-academy
export FLOWCEPT_SETTINGS_PATH=$PWD/setup/flowcept_settings.yaml
```

(`setup/install.sh` runs `conda env create -f setup/environment.yml` then
`pip install -e .`; re-running reuses an existing env.)

`flowcept_settings.yaml` is the **offline** profile: provenance is written to a
JSONL buffer — no Redis/Mongo needed. Each run writes its `flowcept_buffer.jsonl`,
perf CSV, and `<id>_card.md` into a fresh `runs/<id>_<date-time>/` under the
exercise folder.

## LLM backend

Checked in priority order (first match wins):

| Condition | Backend |
|---|---|
| `ARGO_USER` set | ANL **Argo** gateway, native tool calling |
| else `OPENAI_API_KEY` set | **OpenAI** (`api.openai.com`, model `OPENAI_MODEL`, default `gpt-4o-mini`), native tool calling |
| else | **local CPU** model (`Qwen/Qwen2.5-0.5B-Instruct`; `FLOWCEPT_TUTORIAL_MODEL` to change) |
| `FLOWCEPT_TUTORIAL_LLM=argo\|openai\|local` | force a backend (no mock; raises if none is usable) |

## Inspect / query provenance

After running an exercise, explore the buffer it wrote in its folder:

```bash
cd exercises/local/06-llm && python solution.py          # writes runs/06-llm_<date-time>/
python ../../../provenance/query.py runs/06-llm_*         # interactive: df, prov, ask("...")
python ../../../provenance/query.py runs/06-llm_* --ask "how many LLM calls per agent?"
```

`ask("...")` translates natural language to pandas via the LLM (Argo → OpenAI →
local, in priority order). See `provenance/README.md`.
