# Aurora exercises (ALCF)

The same eight examples as [`../local`](../local/README.md), set up to run on
**Aurora**. Each folder adds a `submit.pbs`; all of them (including 07) source the
shared `env.sh` here (ALCF `frameworks` module, the single `flowcept-academy` conda
env, an **offline** LLM that reads ALCF's pre-staged weights, and Flowcept's offline
settings).

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
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/$USER/envs/flowcept-academy
# ^ add to ~/.bashrc so batch jobs inherit it

bash setup/install.sh aurora          # clones the frameworks base + adds the delta
source exercises/aurora/env.sh        # modules + conda env + offline LLM + settings
```

**No model is downloaded.** All LLM usage reads ALCF's read-only staged hub at
`/flare/datasets/model-weights` (the same weights vLLM serves). `env.sh` points
`HF_HOME` there and sets `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`, so the compute
nodes load `meta-llama/Llama-3.1-8B-Instruct` **offline** — no Argo, no network, no
pre-cache step. Do **not** export your own `HF_HOME`; that would point the stack away
from the staged hub and offline loads would fail. If `FLOWCEPT_ENV_PREFIX` is unset it
falls back to `$REPO/envs/flowcept-academy` and warns if nothing is built there.

> **No local/CPU model on Aurora.** Every LLM call — the 06/07/08 agents **and**
> `query.py --ask` — goes through **vLLM on the node's GPUs**, serving the ALCF-staged
> weights offline; there is no `transformers`-on-CPU fallback here. So before anything
> that needs an LLM (including `--ask`), bring the server up with
> `source ../vllm_serve.sh && vllm_start`. `env.sh` defaults the backend to `vllm`. To
> serve a different staged model, set `FLOWCEPT_TUTORIAL_MODEL`/`VLLM_MODEL` to one that
> actually exists under `$HF_HOME/hub`.

> **Exercise 07 chemistry, if conda-forge can't solve against the clone.** If
> `install.sh` warns that `xtb-python`/`rdkit`/`ase` didn't solve, build a tiny
> standalone env just for the chemistry and point 07 at it — 01–06/08 are unaffected:
> ```bash
> conda create -p /lus/flare/projects/ATPESC2026/prov/$USER/envs/fca-xtb -c conda-forge \
>   --yes python=3.11 xtb-python rdkit ase
> ```
> (07's `submit.pbs` already falls back to `conda run -p "$FLOWCEPT_ENV_PREFIX"`; for a
> separate chemistry env, run 07 under that env or add its `xtb` to `PYTHONPATH`.)

### One shared env for the whole project

Build it **once**, into group-writable project space rather than a `$USER` directory:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/envs/flowcept-academy
bash setup/install.sh aurora --shared     # clones the base, adds the delta
source exercises/aurora/env.sh
```

`install.sh --shared` sets `umask 002` and setgid so everything lands in the project
group, then makes the env **group-readable** (`g+rX`). There is no shared model cache to
manage — all LLM usage reads ALCF's staged hub, which is already shared and read-only
for everyone. It also installs the tutorial library non-editable, so the shared env does
not point back at the builder's clone; re-run the same command to republish after
editing `flowcept_academy/`.

Everyone else then adds one line to `~/.bashrc` and never runs the installer:

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/envs/flowcept-academy
```

and per session just `source exercises/aurora/env.sh`. Each user still needs their own
clone of this repo — exercises write `runs/` next to the script being run — but the
multi-GB env is built once for the group.

> At large node counts, importing Python packages from a home or Lustre-backed env
> gets slow; ALCF recommends [Copper](https://docs.alcf.anl.gov/aurora/data-management/copper/)
> past ~1000 nodes. Not a concern for these single-node exercises.

## Run an example

Batch (`submit.pbs` already has `-A ATPESC2026`):

```bash
cd exercises/aurora/01-actor-client
qsub submit.pbs                       # runs solution.py on a compute node
```

Each run writes to its own `runs/<id>_<date-time>/` in the example folder
(`flowcept_buffer.jsonl`, perf CSV, `<id>_card.md`). Interactive: grab a node
(`qsub -I -A ATPESC2026 -q debug -l select=1 -l walltime=00:30:00 -l
filesystems=home:flare`), `source ../env.sh`, then work through `python
exercise.py` step by step.

## Then query it

The plain query REPL uses no LLM. `--ask` (natural-language questions) does, and on
Aurora that means **vLLM must be running** — there is no CPU fallback. From a compute
node (interactive or inside a job), start the server first, then ask:

```bash
source ../vllm_serve.sh && vllm_start                 # ALCF-staged model on the GPUs, offline
python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
```

Without `--ask`, no server is needed:

```bash
python ../../../provenance/query.py runs/<id>_*       # structured queries, no LLM
```

Examples 05 and 07 need the `parsl` / `langgraph` extras, already installed by
`setup/install.sh`. See the [exercises overview](../README.md).

## LLMs on Aurora: vLLM on the node's own GPUs

Compute nodes reach neither Argo nor `api.openai.com`, and there is **no CPU/local
model** on Aurora — so **every** LLM call (the 06/07/08 agents and `query.py --ask`)
goes through vLLM on the node's own GPUs. vLLM ships in the `frameworks` module and
reads weights straight from ALCF's staged hub at `/flare/datasets/model-weights`, so
nothing is downloaded and no external network is touched. It also emits real tool
calls (which example 07 requires). vLLM speaks the OpenAI API, so
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
| `VLLM_MODEL` | `meta-llama/Llama-3.1-8B-Instruct` | ALCF-staged; under ~20B in bf16 fits one 64 GB tile |
| `VLLM_TOOL_PARSER` | `llama3_json` | **Must match the model family** — `hermes` for Qwen |
| `VLLM_TP` | `1` | Tiles; raise only for larger models |
| `VLLM_PORT` | `8000` | |
| `FLOWCEPT_USE_VLLM` | `1` | `0` skips starting vLLM — then set `FLOWCEPT_TUTORIAL_LLM=argo ARGO_USER=...` (there is no CPU fallback) |

The parser matters: with the wrong one the server runs fine but never produces a
parseable tool call, so 07 retries a few times (~3) and then fails. Startup costs
~2–5 minutes and one GPU tile, which is why 01–05 (no LLM) don't start it — the
walltime in 06/07/08's `submit.pbs` is already raised to account for it.

### The XPU model-inspection SIGSEGV (handled automatically)

On Aurora's XPU, `vllm serve` runs a **model-architecture inspection** step that spawns
a helper subprocess (`python -m vllm.model_executor.models.registry`). That subprocess
**segfaults (SIGSEGV)**, and vLLM surfaces it as:

```
Model architectures ['LlamaForCausalLM'] failed to be inspected
... pydantic ... validation error for ModelConfig
```

This is a known frameworks issue — ALCF ships a reproducer + fix in a directory named,
literally, `xpu-model-inspection-hidden-sigsegv`
([argonne-lcf/frameworks-sdk](https://github.com/argonne-lcf/frameworks-sdk)). The fix:
build vLLM's modelinfo cache **in-process** (which never spawns the crashing subprocess),
then let `vllm serve` reuse it — a cache hit skips inspection entirely.

**You don't run anything by hand.** `vllm_start` primes the cache automatically before
serving: it reads the served model's architecture from the staged config (offline),
then runs the vendored builder with the **frameworks** python:

```
>> priming vLLM modelinfo cache (avoids the XPU inspection SIGSEGV)
>>   VLLM_CACHE_ROOT=~/.cache/vllm  arch=LlamaForCausalLM
[OK] LlamaForCausalLM -> vllm.model_executor.models.llama:LlamaForCausalLM
```

Priming and serving use the same `VLLM_CACHE_ROOT` (default `~/.cache/vllm`; point it at
project space for a shared setup — it must be **writable**, unlike the read-only
`HF_HOME` hub). The builder lives at
[`vllm_wa/vllm_build_all_modelinfo_caches.py`](vllm_wa/vllm_build_all_modelinfo_caches.py)
(vendored from frameworks-sdk, with `vllm_make_modelinfo_cache.py` and a reproducer).

To prime by hand (e.g. for a shared cache, once per `VLLM_CACHE_ROOT`), use the
**frameworks** python — the one whose shebang the `vllm` binary carries, not the tutorial
env's:

```bash
export VLLM_CACHE_ROOT=/lus/flare/projects/ATPESC2026/prov/vllm_cache   # shared, writable
"$(sed -n '1s/^#!//p' "$(command -v vllm)")" \
    vllm_wa/vllm_build_all_modelinfo_caches.py --arch LlamaForCausalLM
```

> The benign `Permission denied: .../.no_exist/...preprocessor_config.json` lines during
> startup are HuggingFace failing to write negative-cache markers into the read-only
> staged hub. vLLM ignores them and continues; they are not the SIGSEGV.
