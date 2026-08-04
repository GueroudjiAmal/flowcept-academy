# Setup

**One conda env for the whole tutorial** (all 8 exercises). Example 07 needs real
GFN2-xTB chemistry (`rdkit` + `xtb-python`, conda-forge only), so everything uses
conda — no venv, no per-exercise env.

`setup/install.sh` has two modes; with no argument it picks `aurora` when
`/soft/modulefiles` exists and `local` otherwise. Both run `conda env create -f
setup/environment.yml` then `pip install -e .`, and re-running reuses an existing env.

## `local` — laptop / workstation

Needs conda or miniforge on `PATH`. Builds the env **by name**:

```bash
bash setup/install.sh local
conda activate flowcept-academy
export FLOWCEPT_SETTINGS_PATH=$PWD/setup/flowcept_settings.yaml
```

## `aurora` — ALCF Aurora

Follows the [ALCF Python-on-Aurora docs](https://docs.alcf.anl.gov/aurora/data-science/python/):
conda comes from the `frameworks` module, and the env is built at an explicit
`--prefix` rather than by name. Run this on a **login node** (compute nodes have no
internet):

```bash
# point the env at project space -- torch + transformers + rdkit + xtb run to
# several GB, which will blow through your home quota (check with `myquota`)
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/$USER/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/<project>/$USER/hf_cache     # model cache, same reason

bash setup/install.sh aurora
```

Put both exports in your `~/.bashrc` so batch jobs see them —
[`exercises/aurora/env.sh`](../exercises/aurora/env.sh) reads `FLOWCEPT_ENV_PREFIX`
to activate the env, and falls back to `$REPO/envs/flowcept-academy` if it is unset.
Then, per session:

```bash
source exercises/aurora/env.sh      # modules + conda activate + offline LLM + settings
```

### One env shared by the whole project group

Add `--shared` and point the prefix at group-writable project space instead of a
`$USER` directory:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/shared/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/<project>/shared/hf_cache
bash setup/install.sh aurora --shared
```

The env comes out group-readable (not writable — the owner rebuilds it), the HF cache
group-writable, and the tutorial library is installed non-editable so it does not
depend on the builder's clone. Everyone else exports the same two variables and skips
the installer entirely.

See [`exercises/aurora/README.md`](../exercises/aurora/README.md) for pre-caching the
LLM, the shared-env details, and submitting jobs.

`flowcept_settings.yaml` is the **offline** profile: provenance is written to a
JSONL buffer — no Redis/Mongo needed. Each run writes its `flowcept_buffer.jsonl`,
perf CSV, and `<id>_card.md` into a fresh `runs/<id>_<date-time>/` under the
exercise folder.

## LLM backend

Checked in priority order (first match wins):

| Condition | Backend |
|---|---|
| `ARGO_USER` set | ANL **Argo** gateway, native tool calling |
| else `VLLM_BASE_URL` / `OPENAI_BASE_URL` set | **vLLM** — a server you run yourself (model `VLLM_MODEL`), native tool calling. This is the Aurora path: see [`exercises/aurora/vllm_serve.sh`](../exercises/aurora/vllm_serve.sh) |
| else `OPENAI_API_KEY` set | **OpenAI** (`api.openai.com`, model `OPENAI_MODEL`, default `gpt-4o-mini`), native tool calling |
| else | **local CPU** model (`Qwen/Qwen2.5-0.5B-Instruct`; `FLOWCEPT_TUTORIAL_MODEL` to change) |
| `FLOWCEPT_TUTORIAL_LLM=argo\|vllm\|openai\|local` | force a backend (no mock; raises if none is usable) |

On Aurora, compute nodes reach neither Argo nor OpenAI, so examples 06/07/08 use the
**vLLM** row — a model served on the node's own GPUs from ALCF's staged weights, no
network at all. See [`exercises/aurora/README.md`](../exercises/aurora/README.md#llms-on-aurora-vllm-on-the-nodes-own-gpus).

## Inspect / query provenance

After running an exercise, explore the buffer it wrote in its folder:

```bash
cd exercises/local/06-llm && python solution.py          # writes runs/06-llm_<date-time>/
python ../../../provenance/query.py runs/06-llm_*         # interactive: df, prov, ask("...")
python ../../../provenance/query.py runs/06-llm_* --ask "how many LLM calls per agent?"
```

`ask("...")` translates natural language to pandas via the LLM (Argo → vLLM → OpenAI →
local, in priority order). See `provenance/README.md`.
