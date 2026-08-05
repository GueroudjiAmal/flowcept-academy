# Aurora exercises (ALCF)

The same eight examples as [`../local`](../local/README.md), set up to run on
**Aurora**. Each folder adds a `submit.pbs`; all of them (including 07) source the
shared `env.sh` here (ALCF `frameworks` module, the single `flowcept-academy` conda
env, an **offline** LLM that reads ALCF's pre-staged weights, and Flowcept's offline
settings).

## Students: use the shared env (don't build anything)

If your instructor (or a teammate) already built the env in **shared project space**,
you do **not** run `install.sh` and you download nothing. You need exactly two things:

1. **Your own clone of this repo** — exercises write `runs/<id>_<date-time>/` next to
   the script you run, so you need a writable copy. (The shared *env* is read-only and
   lives elsewhere; only the code needs to be yours.)
2. **One environment variable** pointing at the shared env, then source `env.sh`:

```bash
# the shared env your instructor built (literal path -- NOT $USER; confirm it with them):
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/agueroudji/envs/flowcept-academy
# ^ add this line to ~/.bashrc so batch jobs (and every new shell) inherit it

source exercises/aurora/env.sh        # activates the shared env + offline LLM + settings
```

`env.sh` activates whatever `FLOWCEPT_ENV_PREFIX` points at (stacked on the `frameworks`
module) and sets the offline-LLM + Flowcept settings — nothing else to configure. That's
it: skip straight to **[Run an example](#run-an-example)** (batch) or
**[Interactive mode](#interactive-mode-compute-node)**. For the LLM examples (06/07/08)
`vllm_start` still primes its per-user modelinfo cache under `$HOME/.cache/vllm` the first
time you launch a server — that just works, no setup.

Everything below (building the env) is **only for whoever sets it up for the group** —
students can ignore it.

## Building the env (once, for the group — on a login node)

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

Everyone else then adds one line to `~/.bashrc` and never runs the installer — the
**literal** path to wherever it was built (e.g. under the builder's `$USER`, not their own):

```bash
export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/agueroudji/envs/flowcept-academy
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

The job sources `env.sh`, runs `solution.py`, and writes everything to one
`runs/<id>_<date-time>/` in the example folder — the job's own `job.out`/`job.err`
land there too, alongside `flowcept_buffer.jsonl`, the perf CSV, and `<id>_card.md`
(`submit.pbs` pre-creates the dir and exports `FLOWCEPT_RUN_DIR`, which
`util.new_run_dir()` honors). For 06/07/08 the job also starts vLLM on the node's GPUs
(see below); 01–05 use no LLM.

To step through an exercise by hand instead of submitting a job, use **interactive
mode** (next section).

## Interactive mode (compute node)

Batch (`qsub submit.pbs`) is the hands-off path: it does everything below for you and
you read the results afterward. **Interactive mode** is for working through
`exercise.py` one STEP at a time, or for iterating on the query tool — you get a shell
*on the compute node itself*.

**1. Grab a node** (from a login node). `debug` gives 1 node for up to 1 h; drop the
`filesystems` you don't need:

```bash
qsub -I -A ATPESC2026 -q debug -l select=1 -l walltime=01:00:00 -l filesystems=home:flare
```

You land in a shell **on the node**. Everything from here runs there.

**2. Set up the environment** (every fresh shell needs this):

```bash
cd <repo>/exercises/aurora/06-llm      # whichever example
source ../env.sh                        # frameworks module + conda env + offline LLM + settings
```

**3. Start vLLM — only for 06/07/08** (01–05 use no LLM, skip this):

```bash
source ../vllm_serve.sh
vllm_start        # primes the modelinfo cache (dodges the XPU SIGSEGV), serves the
                  # ALCF-staged model on the GPUs, then exports VLLM_BASE_URL. ~2–5 min.
```

`vllm_start` blocks until `/v1/models` answers and prints `>> vLLM ready after Ns`. It
leaves the server running in the background for the rest of your session; it is torn
down automatically on shell/job exit, or explicitly with `vllm_stop`. See
[*LLMs on Aurora*](#llms-on-aurora-vllm-on-the-nodes-own-gpus) below for how it works
and [*The XPU model-inspection SIGSEGV*](#the-xpu-model-inspection-sigsegv-handled-automatically)
for the cache-priming detail.

**4. Run the exercise.** Either step through it (uncomment one `STEP` block at a time
in `exercise.py`) or run the fully-instrumented harness:

```bash
python exercise.py          # STEP-by-STEP: baseline, then uncomment STEP 1..N and re-run
# or
python solution.py          # all steps at once (same thing the batch job runs)
```

Each run creates its own `runs/<id>_<date-time>/` right here in the example folder.

**5. Query it** — same shell, vLLM already up (see the next section):

```bash
python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
```

**6. Done:** `vllm_stop` (optional — happens on exit anyway), then `exit` to release the
node.

> The whole batch flow is just steps 2–5 wrapped in `submit.pbs`. Interactive mode runs
> the identical `env.sh` / `vllm_serve.sh` / scripts — nothing is different except that
> *you* type the commands and see output live.

## Then query it

The plain query REPL uses no LLM. `--ask` (natural-language questions) does, and on
Aurora that means **vLLM must be running** — there is no CPU fallback. From a compute
node (interactive or inside a job), start the server first, then ask:

```bash
source ../vllm_serve.sh && vllm_start                 # ALCF-staged model on the GPUs, offline
python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
```

**Each shell needs the routing env.** `VLLM_BASE_URL` / `FLOWCEPT_TUTORIAL_LLM=vllm` are
exported into the shell that starts the server, so a **new** shell won't have them and
`--ask` would hit `vLLM backend selected but no endpoint`. The fix is automatic: in any
new shell, once a server is up on the node,

```bash
source ../env.sh
source ../vllm_serve.sh     # sees the running server and routes THIS shell to it
```

is all you need — **sourcing `vllm_serve.sh` adopts an already-running server** and
exports the full routing env (`VLLM_BASE_URL`, `OPENAI_API_KEY=EMPTY`, `VLLM_MODEL`,
unsets `ARGO_USER`). You only call `vllm_start` when you actually want to *launch* a
server; it too adopts rather than double-starts if one is already up.

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
