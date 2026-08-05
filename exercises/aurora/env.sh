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
#   export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/$USER/envs/flowcept-academy

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
    echo "!!     export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/envs/flowcept-academy"
    echo "!! Otherwise build your own:  bash setup/install.sh aurora"
fi

# The frameworks module sets ONEAPI_DEVICE_SELECTOR="opencl:gpu;level_zero:gpu",
# which makes dpctl/dpnp report 24 devices. This tutorial is CPU-only so it does not
# matter; if you add GPU work, uncomment:
#   export ONEAPI_DEVICE_SELECTOR=level_zero:gpu

# --- LLM: ALCF's pre-staged weights, fully offline -------------------------
# Nothing is downloaded. HF_HOME points at ALCF's read-only staged hub under
# /flare/datasets/model-weights (same one vLLM reads), and offline flags force the
# HuggingFace stack to load only from there -- so the compute nodes never touch the
# network. The tutorial's "local" backend loads FLOWCEPT_TUTORIAL_MODEL from that hub;
# it must be a model actually staged there (see the ALCF Aurora vLLM docs / `ls
# $HF_HOME/hub`). NOTE: the local backend runs via `transformers` on CPU -- an 8B is
# slow there, so this is only the FLOWCEPT_USE_VLLM=0 opt-out and query.py's ask();
# 06/07/08 serve the same weights fast on the GPUs via vLLM (below).
export HF_HOME="${HF_HOME:-/flare/datasets/model-weights}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export FLOWCEPT_TUTORIAL_MODEL="${FLOWCEPT_TUTORIAL_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
export FLOWCEPT_TUTORIAL_LLM=local

# --- Flowcept: offline (no Redis/Mongo); records -> flowcept_buffer.jsonl --
export FLOWCEPT_SETTINGS_PATH="$REPO/setup/flowcept_settings.yaml"

# --- LLM for exercises 06/07/08: vLLM on the node's GPUs (default) ----------
# 06/07/08 use an LLM; their submit.pbs serve a real, tool-capable model on this
# node's own GPUs via `source ../vllm_serve.sh && vllm_start` (the same ALCF-staged
# weights, no network). vllm_start exports FLOWCEPT_TUTORIAL_LLM=vllm and
# VLLM_BASE_URL, overriding the `local` default set above. See
# exercises/aurora/README.md ("LLMs on Aurora").
#   * 07 REQUIRES tool calling -- its LangGraph tool_calling node retries a few times
#     and then fails unless the model emits a parseable tool call.
#   * 06/08 default to vLLM too; set FLOWCEPT_USE_VLLM=0 to fall back to the staged
#     model above on CPU via transformers (much slower, weaker, no tool calls).
# Alternative to vLLM, if the compute node reaches the ANL gateway (native tool calls):
#         export ARGO_USER=<your_anl_username> FLOWCEPT_USE_VLLM=0
# Examples 01-05 use no LLM (03/05 only offload compute) and ignore all of this.

# Exported so each submit.pbs can fall back to `conda run -p "$FLOWCEPT_ENV_PREFIX"`.
export FLOWCEPT_ENV_PREFIX="$ENV_PREFIX"

echo "env ready: conda=$ENV_PREFIX  LLM=local(offline)  flowcept=offline"
