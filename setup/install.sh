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
# aurora -- loads the ALCF `frameworks` module for conda, then builds the env at an
#           explicit --prefix (ALCF's documented recipe: `conda create --prefix ...`).
#           Set FLOWCEPT_ENV_PREFIX to a project-space path so the multi-GB env and
#           the HF model cache stay off your home quota, e.g.
#             export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/$USER/envs/flowcept-academy
#
# --shared -- ONE env for everyone on the project, built once by whoever runs this:
#   * env prefix must be group-writable project space, NOT a per-user directory, e.g.
#       export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/shared/envs/flowcept-academy
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
        command -v conda >/dev/null || { echo "conda not found on PATH; install miniforge"; exit 1; }
        TARGET=(-n "$ENV")
        EXISTS() { conda env list | grep -qE "^\s*$ENV\s"; }
        ACTIVATE="conda activate $ENV"
        ;;
    aurora)
        # ALCF Aurora: the `frameworks` module is what puts conda on PATH.
        # Lmod (and conda's module hook) deref $ZSH_EVAL_CONTEXT -- a zsh-only var,
        # unset in bash -> fatal under this script's `set -u`. Define it empty so no
        # deref trips nounset; also drop nounset around the module calls themselves.
        export ZSH_EVAL_CONTEXT="${ZSH_EVAL_CONTEXT:-}"
        set +u
        module use /soft/modulefiles
        module load frameworks
        set -u
        ENV_PREFIX="${FLOWCEPT_ENV_PREFIX:-$REPO/envs/$ENV}"
        case "$ENV_PREFIX" in
            "$HOME"/*|"$HOME")
                echo ">> WARNING: env prefix is under \$HOME ($ENV_PREFIX)."
                echo ">>          torch + transformers + rdkit + xtb run to several GB; check \`myquota\`."
                if (( SHARED )); then
                    echo ">>          \$HOME is NOT group-accessible on Aurora -- a shared env must live in"
                    echo ">>          project space: /lus/flare/projects/<project>/shared/envs/$ENV"
                    exit 1
                fi
                echo ">>          Prefer: export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/\$USER/envs/$ENV"
                ;;
        esac
        if (( SHARED )); then
            # setgid on the parent so the env inherits the project group, and umask 002
            # so conda writes group-readable files as it goes.
            umask 002
            mkdir -p "$(dirname "$ENV_PREFIX")"
            chmod g+s "$(dirname "$ENV_PREFIX")" 2>/dev/null \
                || echo ">> NOTE: could not setgid $(dirname "$ENV_PREFIX") -- check the group owner yourself"
            echo ">> shared build: group=$(stat -c %G "$(dirname "$ENV_PREFIX")")  prefix=$ENV_PREFIX"
        fi
        mkdir -p "$(dirname "$ENV_PREFIX")"
        TARGET=(-p "$ENV_PREFIX")
        EXISTS() { [[ -d "$ENV_PREFIX/conda-meta" ]]; }
        ACTIVATE="conda activate $ENV_PREFIX"
        ;;
    *)
        echo "usage: bash setup/install.sh [local|aurora] [--shared]"; exit 2
        ;;
esac

echo ">> mode: $MODE"
source "$(conda info --base)/etc/profile.d/conda.sh"

# Build the single env (rdkit + xtb for ex 07; agents/LangGraph/LLM for the rest).
if EXISTS; then
    echo ">> conda env already exists -- reusing it (delete with: conda env remove ${TARGET[*]})"
else
    conda env create "${TARGET[@]}" -f "$REPO/setup/environment.yml"
fi

# Install the tutorial library itself into the env. A shared env must NOT be an
# editable install -- that would point every group member at the builder's clone.
if (( SHARED )); then
    conda run --no-capture-output "${TARGET[@]}" pip install "$REPO"
    # ...and force a fresh copy, so re-running after editing flowcept_academy/
    # actually republishes it (pip would otherwise see the same version and skip).
    conda run --no-capture-output "${TARGET[@]}" pip install --force-reinstall --no-deps "$REPO"
else
    conda run --no-capture-output "${TARGET[@]}" pip install -e "$REPO"
fi

# Offline Flowcept settings (no Redis/Mongo; records -> flowcept_buffer.jsonl).
mkdir -p "$HOME/.flowcept" && cp "$REPO/setup/flowcept_settings.yaml" "$HOME/.flowcept/settings.yaml"

conda run --no-capture-output "${TARGET[@]}" python -c \
  "from flowcept_academy import util; print('LLM backend:', util.which_backend(), '| local model:', util.DEFAULT_CHAT_MODEL)"

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
    echo ">> Pre-cache the CPU fallback LLM on this login node (compute nodes have no internet):"
    echo "     source exercises/aurora/env.sh && python -c \"from flowcept_academy.util import chat; print(chat('hi'))\""
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
    echo ">> Start here:      cd exercises/aurora/01-actor-client && qsub submit.pbs   (edit -A <project> first)"
else
    echo ">> Start here:      cd exercises/local/01-actor-client && python exercise.py"
fi
echo ">> Reference:       python solution.py   (every provenance step enabled)"
echo ">> LLM example:     cd exercises/local/06-llm && python solution.py"
echo ">> Real chemistry:  cd exercises/local/07-mol-design && python solution.py  (set ARGO_USER first)"
echo ">> Use Argo instead of the local LLM:  export ARGO_USER=<anl-username>"
