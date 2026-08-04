# Aurora exercises (ALCF)

The same eight examples as [`../local`](../local/README.md), set up to run on
**Aurora**. Each folder adds a `submit.pbs`; all of them (including 07) source the
shared `env.sh` here (ALCF `frameworks` module, the single `flowcept-academy` conda
env, an **offline** local CPU LLM, and Flowcept's offline settings).

## One-time setup (on a login node)

Per the [ALCF Python-on-Aurora docs](https://docs.alcf.anl.gov/aurora/data-science/python/),
conda comes from the `frameworks` module and the env is built at an explicit
`--prefix`. Point that prefix at **project space** — the env (torch, transformers,
rdkit, xtb) and the model cache together run to several GB and will not fit a home
quota (`myquota`):

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/$USER/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/<project>/$USER/hf_cache
# ^ add both to ~/.bashrc so batch jobs inherit them

bash setup/install.sh aurora          # module load frameworks + conda env create --prefix
source exercises/aurora/env.sh        # modules + conda env + offline LLM + settings
# pre-cache the local LLM while you still have internet (login nodes have it):
python -c "from flowcept_academy.util import chat; print(chat('hi'))"
```

`env.sh` sets `HF_HUB_OFFLINE=1` (and defaults `HF_HOME` to `$REPO/hf_cache` if you
did not export it), so once the model is cached the compute nodes read it offline —
no Argo, no network. If `FLOWCEPT_ENV_PREFIX` is unset it falls back to
`$REPO/envs/flowcept-academy` and warns if nothing is built there.

### One shared env for the whole project

Build it **once**, into group-writable project space rather than a `$USER` directory:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/shared/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/<project>/shared/hf_cache
bash setup/install.sh aurora --shared
source exercises/aurora/env.sh
python -c "from flowcept_academy.util import chat; print(chat('hi'))"   # fills the shared cache
```

`--shared` sets `umask 002` and setgid so everything lands in the project group, then
makes the env **group-readable** (`g+rX`) and the HF cache **group-writable**
(`g+rwX` — `huggingface_hub` writes lock files even on a cache hit). It also installs
the tutorial library non-editable, so the shared env does not point back at the
builder's clone; re-run the same command to republish after editing
`flowcept_academy/`.

Everyone else then adds two lines to `~/.bashrc` and never runs the installer:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/shared/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/<project>/shared/hf_cache
```

and per session just `source exercises/aurora/env.sh`. Each user still needs their own
clone of this repo — exercises write `runs/` next to the script being run — but the
multi-GB env and model cache are downloaded once for the group.

> At large node counts, importing Python packages from a home or Lustre-backed env
> gets slow; ALCF recommends [Copper](https://docs.alcf.anl.gov/aurora/data-management/copper/)
> past ~1000 nodes. Not a concern for these single-node exercises.

## Run an example

Batch (edit `-A <project>` in `submit.pbs` first):

```bash
cd exercises/aurora/01-actor-client
qsub submit.pbs                       # runs solution.py on a compute node
```

Each run writes to its own `runs/<id>_<date-time>/` in the example folder
(`flowcept_buffer.jsonl`, perf CSV, `<id>_card.md`). Interactive: grab a node
(`qsub -I -A <project> -q debug -l select=1 -l walltime=00:30:00 -l
filesystems=home:flare`), `source ../env.sh`, then work through `python
exercise.py` step by step.

## Then query it

```bash
python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
```

Examples 05 and 07 need the `parsl` / `langgraph` extras, already installed by
`setup/install.sh`. See the [exercises overview](../README.md).

## LLMs on Aurora: vLLM on the node's own GPUs

Compute nodes reach neither Argo nor `api.openai.com`, and the CPU fallback
(`Qwen2.5-0.5B-Instruct` through transformers) is slow and **cannot emit tool
calls** — which example 07 requires. So examples 06/07/08 serve a real model
*locally*: vLLM ships in the `frameworks` module and reads weights straight from
ALCF's staged hub at `/flare/datasets/model-weights`, so nothing is downloaded and
no external network is touched. vLLM speaks the OpenAI API, so
[`flowcept_academy.util`](../../flowcept_academy/util.py) routes to it through the
same `ChatOpenAI` path Argo/OpenAI use — **the agent code is unchanged**.

[`vllm_serve.sh`](vllm_serve.sh) handles this; the 06/07/08 `submit.pbs` already
call it:

```bash
source ../vllm_serve.sh
vllm_start            # blocks until the server answers, then exports the routing env
python solution.py
vllm_stop             # also runs automatically on job exit
```

`vllm_start` exports `FLOWCEPT_TUTORIAL_LLM=vllm` and `VLLM_BASE_URL`, which is all
`which_backend()` needs. Tunables (all overridable before sourcing):

| Variable | Default | Notes |
|---|---|---|
| `VLLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | Under ~20B in bf16 fits one 64 GB tile |
| `VLLM_TOOL_PARSER` | `hermes` | **Must match the model family** — `llama3_json` for Llama-3.1 |
| `VLLM_TP` | `1` | Tiles; raise only for larger models |
| `VLLM_PORT` | `8000` | |
| `FLOWCEPT_USE_VLLM` | `1` | `0` → fall back to the CPU model (06/08 only) |

The parser matters: with the wrong one the server runs fine but never produces a
parseable tool call, and 07 retries forever. Startup costs ~2–5 minutes and one GPU
tile, which is why 01–05 stay on the CPU model — the walltime in 06/07/08's
`submit.pbs` is already raised to account for it.

### One-time: populate vLLM's modelinfo cache

vLLM has a documented first-run bug filling `modelinfos` in `VLLM_CACHE_ROOT`
(default `~/.cache/vllm`); an unpopulated cache makes the server exit at startup with
`validation error for ModelConfig`. Fix it once, from a node with proxies set, using
`vllm_build_all_modelinfo_caches.py` from
[argonne-lcf/frameworks-sdk](https://github.com/argonne-lcf/frameworks-sdk):

```bash
export VLLM_CACHE_ROOT=/lus/flare/projects/<project>/shared/vllm_cache   # shared setup
python vllm_build_all_modelinfo_caches.py
```

Re-run it any time you move `VLLM_CACHE_ROOT`. `vllm_start` prints a pointer to this
section if the server dies during startup.
