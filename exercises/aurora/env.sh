# Source this on Aurora before running ANY exercise:  source ../env.sh
# It is also sourced by every exercise's submit.pbs (all 8, including 07).
#
# ONE conda env for the whole tutorial -- built once on a login node by
#   bash setup/install.sh aurora
# Sets up: ALCF frameworks module, the conda env, an OFFLINE local CPU LLM (no Argo
# needed on compute nodes), and Flowcept's offline settings.
#
# Per the ALCF Python-on-Aurora docs the env lives at an explicit --prefix, not a
# name. Export the SAME FLOWCEPT_ENV_PREFIX you used at install time (put it in your
# ~/.bashrc so batch jobs see it too); otherwise this falls back to $REPO/envs/.
#   export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/$USER/envs/flowcept-academy

# This file must be SOURCED, not executed. It runs `conda activate` and `export`s
# INTO your shell; `bash env.sh` runs in a subshell where those changes die on exit
# (and `module` isn't even defined in a non-login shell). Use:  source ../env.sh
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "!! Don't execute this -- SOURCE it:   source ${BASH_SOURCE[0]}" >&2
    exit 1
fi

# Lmod (and conda's module hook) dereference $ZSH_EVAL_CONTEXT -- a zsh-only var,
# unset in bash -- which is FATAL under a caller's `set -u`. Define it empty so no
# deref trips nounset, here or in the module/conda subshells this spawns. (A real
# zsh sets its own, so an inherited empty value is harmless.)
export ZSH_EVAL_CONTEXT="${ZSH_EVAL_CONTEXT:-}"

# Repo root = two levels up from exercises/aurora/
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_PREFIX="${FLOWCEPT_ENV_PREFIX:-$REPO/envs/flowcept-academy}"

# --- ALCF modules (provide conda) ------------------------------------------
# Lmod's bash init dereferences $ZSH_EVAL_CONTEXT unguarded, which is FATAL under a
# caller's `set -u` (every submit.pbs runs `set -euo pipefail`; `|| true` does NOT
# rescue a nounset death). Drop nounset around the module calls, then restore it.
_flowcept_had_u=0; if [[ $- == *u* ]]; then _flowcept_had_u=1; fi
set +u
module use /soft/modulefiles 2>/dev/null || true
module load frameworks 2>/dev/null || true
if [[ $_flowcept_had_u == 1 ]]; then set -u; fi
unset _flowcept_had_u

# --- The single conda env (built once by setup/install.sh aurora) ----------
# 'conda activate' needs conda's shell hook; submit.pbs falls back to `conda run`
# if activation doesn't take in a non-interactive job.
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate "$ENV_PREFIX" 2>/dev/null || true

if [[ ! -d "$ENV_PREFIX/conda-meta" ]]; then
    echo "!! no conda env at $ENV_PREFIX"
    echo "!! If your project has a SHARED env, just point at it (and add this to ~/.bashrc):"
    echo "!!     export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/<project>/shared/envs/flowcept-academy"
    echo "!! Otherwise build your own:  bash setup/install.sh aurora"
fi

# The frameworks module sets ONEAPI_DEVICE_SELECTOR="opencl:gpu;level_zero:gpu",
# which makes dpctl/dpnp report 24 devices. This tutorial is CPU-only so it does not
# matter; if you add GPU work, uncomment:
#   export ONEAPI_DEVICE_SELECTOR=level_zero:gpu

# --- LLM: local CPU model, fully offline -----------------------------------
# Pre-cache the model on a login node first (has internet):
#   python -c "from flowcept_academy.util import chat; print(chat('hi'))"
# then compute nodes read it from HF_HOME with HF_HUB_OFFLINE=1.
# Keep this off your home quota too -- set HF_HOME next to the env if the repo
# itself lives in $HOME:
#   export HF_HOME=/lus/flare/projects/<project>/$USER/hf_cache
export HF_HOME="${HF_HOME:-$REPO/hf_cache}"
export HF_HUB_OFFLINE=1
export FLOWCEPT_TUTORIAL_LLM=local

# --- Flowcept: offline (no Redis/Mongo); records -> flowcept_buffer.jsonl --
export FLOWCEPT_SETTINGS_PATH="$REPO/setup/flowcept_settings.yaml"

# --- LLM for exercises 06/07/08: vLLM on the node's GPUs (default) ----------
# 06/07/08 use an LLM; their submit.pbs serve a real, tool-capable model on this
# node's own GPUs via `source ../vllm_serve.sh && vllm_start` (weights from ALCF's
# staged hub, no network). vllm_start exports FLOWCEPT_TUTORIAL_LLM=vllm and
# VLLM_BASE_URL, overriding the offline `local` default set above. See
# exercises/aurora/README.md ("LLMs on Aurora").
#   * 07 REQUIRES tool calling -- its LangGraph tool_calling node retries until the
#     model emits a parseable tool call, which the local 0.5B model never does.
#   * 06/08 default to vLLM too; set FLOWCEPT_USE_VLLM=0 to fall back to the 0.5B
#     CPU model above (faster to start, weaker answers, no tool calls).
# Alternatives to vLLM, if you prefer them (set BEFORE running):
#   (a) Argo (native tool calling), if the compute node reaches the ANL gateway:
#         export ARGO_USER=<your_anl_username> FLOWCEPT_USE_VLLM=0
#   (b) a tool-capable local model, offline (pre-cache it on a login node first):
#         export FLOWCEPT_TUTORIAL_MODEL=Qwen/Qwen2.5-7B-Instruct FLOWCEPT_USE_VLLM=0
# Examples 01-05 use no LLM (03/05 only offload compute) and ignore all of this.

# Exported so each submit.pbs can fall back to `conda run -p "$FLOWCEPT_ENV_PREFIX"`.
export FLOWCEPT_ENV_PREFIX="$ENV_PREFIX"

echo "env ready: conda=$ENV_PREFIX  LLM=local(offline)  flowcept=offline"
