# Aurora exercises (ALCF)

The same eight examples as [`../local`](../local/README.md), set up to run on
**Aurora**. Each folder adds a `submit.pbs`; all of them (including 07) source the
shared `env.sh` here (ALCF `frameworks` module, the single `flowcept-academy` conda
env, an **offline** local CPU LLM, and Flowcept's offline settings).

## One-time setup (on a login node)

On Aurora `conda` comes from the `frameworks` module. Following the ALCF
["Cloning the base Anaconda environment"](https://docs.alcf.anl.gov/polaris/data-science/python/#cloning-the-base-anaconda-environment)
recipe, `install.sh aurora` **clones the frameworks base env** into your `--prefix`
and then adds only the tutorial's delta on top: exercise 07's chemistry
(`xtb-python`, `rdkit`, `ase`) from **conda-forge**, and the agent/LLM stack
(`flowcept`, `academy`, `langchain`, …) with **pip**. Cloning keeps us in conda so
`xtb-python` installs cleanly — there is no PyPI `xtb` wheel for the base's Python 3.12.

Point the prefix at **project space**: a clone of the base is many GB and will not fit
a home quota (`myquota`). ALCF warns the clone is slow — it is a one-time cost.

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC/$USER/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/ATPESC/$USER/hf_cache
# ^ add both to ~/.bashrc so batch jobs inherit them

bash setup/install.sh aurora          # clones the frameworks base + adds the delta
source exercises/aurora/env.sh        # modules + conda env + offline LLM + settings
```

`install.sh` **pre-caches the CPU fallback LLM for you** on the login node (with
internet), so you do **not** run any `chat('hi')` step by hand. `env.sh` then sets
`HF_HUB_OFFLINE=1` (and defaults `HF_HOME` to `$REPO/hf_cache` if you did not export
it), so the compute nodes read that cached model **offline** — no Argo, no network. If
`FLOWCEPT_ENV_PREFIX` is unset it falls back to `$REPO/envs/flowcept-academy` and warns
if nothing is built there.

> **Re-caching by hand.** If you ever need to, do it from a login node with the online
> flags *explicitly overriding* `env.sh` (sourcing `env.sh` first would set
> `HF_HUB_OFFLINE=1` and the download would fail):
> ```bash
> HF_HOME=$HF_HOME HF_HUB_OFFLINE=0 FLOWCEPT_TUTORIAL_LLM=local \
>   python -c "from flowcept_academy.util import chat; chat('hi')"
> ```

> **Exercise 07 chemistry, if conda-forge can't solve against the clone.** If
> `install.sh` warns that `xtb-python`/`rdkit`/`ase` didn't solve, build a tiny
> standalone env just for the chemistry and point 07 at it — 01–06/08 are unaffected:
> ```bash
> conda create -p /lus/flare/projects/ATPESC/$USER/envs/fca-xtb -c conda-forge \
>   --yes python=3.11 xtb-python rdkit ase
> ```
> (07's `submit.pbs` already falls back to `conda run -p "$FLOWCEPT_ENV_PREFIX"`; for a
> separate chemistry env, run 07 under that env or add its `xtb` to `PYTHONPATH`.)

### One shared env for the whole project

Build it **once**, into group-writable project space rather than a `$USER` directory:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC/shared/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/ATPESC/shared/hf_cache
bash setup/install.sh aurora --shared     # clones the base, adds the delta, pre-caches the CPU LLM
source exercises/aurora/env.sh
```

`install.sh --shared` pre-caches the CPU LLM into the shared `HF_HOME` for the whole
group. It sets `umask 002` and setgid so everything lands in the project group, then
makes the env **group-readable** (`g+rX`) and the HF cache **group-writable**
(`g+rwX` — `huggingface_hub` writes lock files even on a cache hit). It also installs
the tutorial library non-editable, so the shared env does not point back at the
builder's clone; re-run the same command to republish after editing
`flowcept_academy/`.

Everyone else then adds two lines to `~/.bashrc` and never runs the installer:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC/shared/envs/flowcept-academy
export HF_HOME=/lus/flare/projects/ATPESC/shared/hf_cache
```

and per session just `source exercises/aurora/env.sh`. Each user still needs their own
clone of this repo — exercises write `runs/` next to the script being run — but the
multi-GB env and model cache are downloaded once for the group.

> At large node counts, importing Python packages from a home or Lustre-backed env
> gets slow; ALCF recommends [Copper](https://docs.alcf.anl.gov/aurora/data-management/copper/)
> past ~1000 nodes. Not a concern for these single-node exercises.

## Run an example

Batch (`submit.pbs` already has `-A ATPESC`):

```bash
cd exercises/aurora/01-actor-client
qsub submit.pbs                       # runs solution.py on a compute node
```

Each run writes to its own `runs/<id>_<date-time>/` in the example folder
(`flowcept_buffer.jsonl`, perf CSV, `<id>_card.md`). Interactive: grab a node
(`qsub -I -A ATPESC -q debug -l select=1 -l walltime=00:30:00 -l
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
parseable tool call, so 07 retries a few times (~3) and then fails. Startup costs
~2–5 minutes and one GPU
tile, which is why 01–05 stay on the CPU model — the walltime in 06/07/08's
`submit.pbs` is already raised to account for it.

### One-time: populate vLLM's modelinfo cache

vLLM has a documented first-run bug filling `modelinfos` in `VLLM_CACHE_ROOT`
(default `~/.cache/vllm`); an unpopulated cache makes the server exit at startup with
`validation error for ModelConfig`. Fix it once, from a node with proxies set, using
`vllm_build_all_modelinfo_caches.py` from
[argonne-lcf/frameworks-sdk](https://github.com/argonne-lcf/frameworks-sdk):

```bash
export VLLM_CACHE_ROOT=/lus/flare/projects/ATPESC/shared/vllm_cache   # shared setup
python vllm_build_all_modelinfo_caches.py
```

Re-run it any time you move `VLLM_CACHE_ROOT`. `vllm_start` prints a pointer to this
section if the server dies during startup.
