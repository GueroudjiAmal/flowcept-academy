#!/bin/bash -l
# One-command setup for the WHOLE tutorial (all 8 exercises), CPU-only.
# ONE conda env -- no venv, no per-exercise env. Run from the repo root:
#
#   bash setup/install.sh                    # auto-detect the mode
#   bash setup/install.sh local              # laptop/workstation: named env in conda's envs dir
#   bash setup/install.sh aurora             # ALCF Aurora: --prefix env, per the ALCF Python docs
#   bash setup/install.sh aurora --shared    # ...built ONCE for the whole project group
#
# local  -- needs conda/miniforge on PATH; builds `flowcept-academy` by name.
# aurora -- loads the ALCF `frameworks` module for conda, then CLONES its base env at
#           an explicit --prefix (ALCF's "Cloning the base Anaconda environment" recipe)
#           and adds the tutorial delta on top.
#           Set FLOWCEPT_ENV_PREFIX to a project-space path so the multi-GB clone and
#           the HF model cache stay off your home quota, e.g.
#             export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/$USER/envs/flowcept-academy
#
# --shared -- ONE env for everyone on the project, built once by whoever runs this:
#   * env prefix must be group-writable project space, NOT a per-user directory, e.g.
#       export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/envs/flowcept-academy
#   * setgid + umask 002 so every file lands in the project group,
#     then `chmod -R g+rX` -> group-READABLE, not group-writable. Rebuilds are the
#     owner's job; a teammate who needs to change it makes their own env.
#   * the tutorial library is installed NON-editable, so the shared env does not point
#     back at the builder's personal clone. Re-run this script after editing
#     flowcept_academy/ to publish the change.
#   * teammates then need only:  export FLOWCEPT_ENV_PREFIX=<same path>
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV=flowcept-academy
MODE="${1:-auto}"
SHARED=0
[[ "${2:-}" == "--shared" ]] && SHARED=1

[[ "$MODE" == auto ]] && { [[ -d /soft/modulefiles ]] && MODE=aurora || MODE=local; }

if (( SHARED )) && [[ "$MODE" != aurora ]]; then
    echo "--shared only applies to the aurora mode"; exit 2
fi

case "$MODE" in
    local)
        # Laptop / workstation: a self-contained conda env from environment.yml
        # (its own torch + the conda-forge rdkit/xtb/ase chemistry for ex 07).
        command -v conda >/dev/null || { echo "conda not found on PATH; install miniforge"; exit 1; }
        ENV_DESC="conda env '$ENV'"
        EXISTS() { conda env list | grep -qE "^\s*$ENV\s"; }
        ACTIVATE="conda activate $ENV"
        ACTIVATE_ENV() { :; }                                   # conda run selects the env; no activation needed
        BUILD_ENV() { conda env create -n "$ENV" -f "$REPO/setup/environment.yml"; }
        PIP()   { conda run --no-capture-output -n "$ENV" pip "$@"; }
        PYRUN() { conda run --no-capture-output -n "$ENV" python "$@"; }
        ;;
    aurora)
        # ALCF Aurora: CLONE the `frameworks` module's base conda env, then build on
        # top -- the ALCF "Cloning the base Anaconda environment" recipe
        # (docs.alcf.anl.gov/polaris/data-science/python). The clone inherits the
        # module's optimized stack, and because it stays CONDA (not a venv on the
        # module) exercise 07's `xtb` installs cleanly from conda-forge -- xtb-python
        # has a py3.12 build, whereas there is NO PyPI wheel for the module's 3.12.
        # We add only the tutorial delta: conda-forge for xtb/rdkit/ase, pip for the
        # rest (setup/requirements-aurora.txt). The module also provides the `vllm`
        # binary that vllm_serve.sh runs as a SEPARATE server for 06/07/08 (the tutorial
        # talks to it over HTTP), so this env needs only a CPU torch (inherited from the
        # clone) for the 0.5B fallback model.
        # NOTE: ALCF warns cloning is slow and multi-GB -- keep ENV_PREFIX in project space.
        #
        # Lmod (and conda's module hook) deref $ZSH_EVAL_CONTEXT -- a zsh-only var,
        # unset in bash -> fatal under this script's `set -u`. Define it empty so no
        # deref trips nounset; also drop nounset around the module calls themselves.
        export ZSH_EVAL_CONTEXT="${ZSH_EVAL_CONTEXT:-}"
        set +u
        module use /soft/modulefiles
        module load frameworks
        # conda's shell functions, so `conda activate` works in this non-interactive
        # script; activate the base env we are about to clone.
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate base
        set -u
        ENV_PREFIX="${FLOWCEPT_ENV_PREFIX:-$REPO/envs/$ENV}"
        case "$ENV_PREFIX" in
            "$HOME"/*|"$HOME")
                echo ">> WARNING: env prefix is under \$HOME ($ENV_PREFIX)."
                echo ">>          a clone of the frameworks base is many GB; check \`myquota\`."
                if (( SHARED )); then
                    echo ">>          \$HOME is NOT group-accessible on Aurora -- a shared env must live in"
                    echo ">>          project space: /lus/flare/projects/ATPESC2026/prov/envs/$ENV"
                    exit 1
                fi
                echo ">>          Prefer: export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/\$USER/envs/$ENV"
                ;;
        esac
        if (( SHARED )); then
            # setgid on the parent so the env inherits the project group, and umask 002
            # so files land group-readable as they are written.
            umask 002
            mkdir -p "$(dirname "$ENV_PREFIX")"
            chmod g+s "$(dirname "$ENV_PREFIX")" 2>/dev/null \
                || echo ">> NOTE: could not setgid $(dirname "$ENV_PREFIX") -- check the group owner yourself"
            echo ">> shared build: group=$(stat -c %G "$(dirname "$ENV_PREFIX")")  prefix=$ENV_PREFIX"
        fi
        mkdir -p "$(dirname "$ENV_PREFIX")"
        ENV_DESC="cloned-base conda env at $ENV_PREFIX (frameworks module)"
        EXISTS() { [[ -d "$ENV_PREFIX/conda-meta" ]]; }
        ACTIVATE="conda activate $ENV_PREFIX"
        ACTIVATE_ENV() { conda activate "$ENV_PREFIX"; }
        BUILD_ENV() {
            # Clone the module's base env (ALCF recipe), then activate it and add the
            # tutorial delta. Cloning is slow -- ALCF says so -- but it is a one-time cost.
            conda create --clone base --prefix "$ENV_PREFIX" --yes
            ACTIVATE_ENV
            echo ">> cloned-base Python: $(python --version 2>&1)"
            # Exercise 07 chemistry from conda-forge (xtb-python builds for py3.12; there
            # is no PyPI wheel). If the solver can't fit them onto the cloned base, warn
            # and continue -- 01-06/08 don't need chemistry.
            if ! conda install --prefix "$ENV_PREFIX" -c conda-forge --yes xtb-python rdkit ase; then
                echo ">> WARN: conda-forge xtb-python/rdkit/ase did not solve against the clone."
                echo ">>       Exercise 07's real GFN2-xTB chemistry is unavailable; 01-06/08 are fine."
                echo ">>       See exercises/aurora/README.md for a standalone conda-xtb fallback env."
            fi
            # Everything else that isn't already in the base: pip on top. (pip skips any
            # requirement the cloned base already satisfies, e.g. torch/numpy/pandas.)
            python -m pip install -r "$REPO/setup/requirements-aurora.txt"
        }
        PIP()   { python -m pip "$@"; }        # clone is activated (built or reused) before use
        PYRUN() { python "$@"; }
        ;;
    *)
        echo "usage: bash setup/install.sh [local|aurora] [--shared]"; exit 2
        ;;
esac

echo ">> mode: $MODE"

# Build the env (or reuse it), then make sure it's active for the steps below.
if EXISTS; then
    echo ">> $ENV_DESC already exists -- reusing it"
else
    BUILD_ENV
fi
ACTIVATE_ENV

# Install the tutorial library itself into the env. A shared env must NOT be an
# editable install -- that would point every group member at the builder's clone.
if (( SHARED )); then
    PIP install "$REPO"
    # ...and force a fresh copy, so re-running after editing flowcept_academy/
    # actually republishes it (pip would otherwise see the same version and skip).
    PIP install --force-reinstall --no-deps "$REPO"
else
    PIP install -e "$REPO"
fi

# Offline Flowcept settings (no Redis/Mongo; records -> flowcept_buffer.jsonl).
mkdir -p "$HOME/.flowcept" && cp "$REPO/setup/flowcept_settings.yaml" "$HOME/.flowcept/settings.yaml"

PYRUN -c \
  "from flowcept_academy import util; print('LLM backend:', util.which_backend(), '| local model:', util.DEFAULT_CHAT_MODEL)"

# --- Offline prep (Aurora): pre-cache the CPU fallback LLM NOW ---------------
# This login node has internet; the compute nodes do NOT, and env.sh sets
# HF_HUB_OFFLINE=1 at run time -- so the 0.5B fallback model must already be on disk
# in HF_HOME. (We force HF_HUB_OFFLINE=0 + FLOWCEPT_TUTORIAL_LLM=local here so the
# fetch actually happens regardless of the caller's shell.) 06/07/08 normally serve a
# bigger model with vLLM instead, but query.py's ask() and the FLOWCEPT_USE_VLLM=0
# fallback use this one; vLLM weights come from ALCF's staged hub -- nothing to fetch.
if [[ "$MODE" == aurora ]]; then
    export HF_HOME="${HF_HOME:-$REPO/hf_cache}"
    mkdir -p "$HF_HOME"
    echo ">> pre-caching the CPU fallback LLM into $HF_HOME (login node, online)..."
    if FLOWCEPT_TUTORIAL_LLM=local HF_HUB_OFFLINE=0 PYRUN -c \
        "from flowcept_academy.util import chat; chat('hi'); print('CPU fallback LLM cached')"; then
        echo ">> cached -- compute nodes can load it offline (HF_HUB_OFFLINE=1)."
    else
        echo ">> WARN: could not pre-cache the CPU LLM (no internet here, or the download failed)."
        echo ">>       06/08's CPU fallback and query.py's ask() will fail offline until it is cached."
        echo ">>       Retry from a login node (note the explicit online flags):"
        echo "           HF_HOME=$HF_HOME HF_HUB_OFFLINE=0 FLOWCEPT_TUTORIAL_LLM=local \\"
        echo "             python -c \"from flowcept_academy.util import chat; chat('hi')\""
    fi
fi

if (( SHARED )); then
    # Group-READABLE (g+rX), deliberately not group-writable: teammates run the env,
    # the owner rebuilds it. Also share the HF weight cache if it is outside the env.
    echo ">> making the env group-readable (this walks a few hundred thousand files)..."
    chmod -R g+rX "$ENV_PREFIX"
    # The HF cache, unlike the env, is group-WRITABLE: huggingface_hub writes lock
    # files under hub/.locks even on a pure cache hit, so a read-only cache can fail
    # for everyone but the owner. It is regenerable, so this is the cheap trade.
    if [[ -n "${HF_HOME:-}" && -d "$HF_HOME" ]]; then
        chmod -R g+rwX "$HF_HOME"
        find "$HF_HOME" -type d -exec chmod g+s {} + 2>/dev/null || true
        echo ">> shared HF cache (group-writable): $HF_HOME"
    fi
fi

echo ">> Done. Activate:  $ACTIVATE"
if (( SHARED )); then
    echo ">>"
    echo ">> Shared env ready. Tell everyone on the project to put these in their ~/.bashrc:"
    echo "     export FLOWCEPT_ENV_PREFIX=$ENV_PREFIX"
    [[ -n "${HF_HOME:-}" ]] && echo "     export HF_HOME=$HF_HOME"
    echo ">> They do NOT re-run this script. Per session they only need:"
    echo "     source exercises/aurora/env.sh"
    echo ">> Each user still needs their own clone of this repo (the exercises write"
    echo ">> runs/ next to the script they run), but the env itself is shared."
    echo ">>"
fi
if [[ "$MODE" == aurora ]]; then
    echo ">> On Aurora, just:  source exercises/aurora/env.sh   (modules + env + offline LLM + settings)"
    echo ">> The CPU fallback LLM was pre-cached above; env.sh then runs it fully offline."
    echo ">>"
    echo ">> Examples 06/07/08 instead serve a real model with vLLM on the compute node's"
    echo ">> GPUs (see exercises/aurora/vllm_serve.sh). Weights come from ALCF's staged hub"
    echo ">> at /flare/datasets/model-weights -- nothing to download. But vLLM's modelinfo"
    echo ">> cache must be populated ONCE, from a node with proxies set, or the server dies"
    echo ">> with 'validation error for ModelConfig':"
    echo "     export VLLM_CACHE_ROOT=\${VLLM_CACHE_ROOT:-\$HOME/.cache/vllm}   # shared env: use project space"
    echo "     # get vllm_build_all_modelinfo_caches.py from argonne-lcf/frameworks-sdk, then:"
    echo "     python vllm_build_all_modelinfo_caches.py"
    echo ">> Re-run that if you ever move VLLM_CACHE_ROOT."
    echo ">> Start here:      cd exercises/aurora/01-actor-client && qsub submit.pbs   (-A ATPESC2026 set)"
else
    echo ">> Start here:      cd exercises/local/01-actor-client && python exercise.py"
fi
echo ">> Reference:       python solution.py   (every provenance step enabled)"
echo ">> LLM example:     cd exercises/local/06-llm && python solution.py"
echo ">> Real chemistry:  cd exercises/local/07-mol-design && python solution.py  (set ARGO_USER first)"
echo ">> Use Argo instead of the local LLM:  export ARGO_USER=<anl-username>"
