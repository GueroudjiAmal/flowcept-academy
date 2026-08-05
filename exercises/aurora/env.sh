# Source this on Aurora before running ANY exercise:  source ../env.sh
# It is also sourced by every exercise's submit.pbs (all 8, including 07).
#
# ONE conda env for the whole tutorial -- built once on a login node by
#   bash setup/install.sh aurora
# Sets up: ALCF frameworks module, the conda env, the OFFLINE vLLM backend (the only
# LLM on Aurora -- served on the node's GPUs by vllm_start), and Flowcept's offline
# settings. There is no local/CPU LLM here; that is the exercises/local/ path.
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
# NOTE: --stack. Per the ALCF vLLM docs, `vllm` lives in the `frameworks` module's base
# env (module load frameworks -> /opt/aurora/.../bin/vllm). A plain `conda activate
# $ENV_PREFIX` REPLACES that base on PATH, so the module's vllm disappears and
# vllm_start can't find it. Stacking keeps the frameworks base underneath, so the
# tutorial env's python (flowcept/academy) is used AND the module's `vllm` binary stays
# reachable for the server (solution.py talks to vLLM over HTTP; it never imports it).
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate --stack "$ENV_PREFIX" 2>/dev/null || true

if [[ ! -d "$ENV_PREFIX/conda-meta" ]]; then
    echo "!! no conda env at $ENV_PREFIX"
    echo "!! If your project has a SHARED env, just point at it (and add this to ~/.bashrc):"
    echo "!!     export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/agueroudji/envs/flowcept-academy"
    echo "!! Otherwise build your own:  bash setup/install.sh aurora"
fi

# The frameworks module sets ONEAPI_DEVICE_SELECTOR="opencl:gpu;level_zero:gpu",
# which makes dpctl/dpnp report 24 devices. This tutorial is CPU-only so it does not
# matter; if you add GPU work, uncomment:
#   export ONEAPI_DEVICE_SELECTOR=level_zero:gpu

# --- LLM: ALCF's pre-staged weights, served offline by vLLM ----------------
# Nothing is downloaded and there is NO local/CPU model on Aurora: every LLM call
# (the 06/07/08 agents AND query.py's --ask) uses an ALCF-staged model under
# /flare/datasets/model-weights, served by vLLM on this node's own GPUs, fully offline.
# HF_HOME points at that read-only hub and the offline flags keep the HuggingFace stack
# from touching the network. FLOWCEPT_TUTORIAL_MODEL / VLLM_MODEL name the staged model
# to serve (it must exist under $HF_HOME/hub -- see the ALCF Aurora vLLM docs / `ls
# $HF_HOME/hub`). The default backend is vLLM (overridable); `vllm_start` (below) brings
# the server up and exports VLLM_BASE_URL so this default resolves.
export HF_HOME="${HF_HOME:-/flare/datasets/model-weights}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export FLOWCEPT_TUTORIAL_MODEL="${FLOWCEPT_TUTORIAL_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
# Keep the vLLM model name in lockstep with the tutorial model so a single override of
# FLOWCEPT_TUTORIAL_MODEL propagates, and util.py's vLLM branch (which reads VLLM_MODEL)
# has the right name even before vllm_serve.sh is sourced. vllm_serve.sh honors this.
export VLLM_MODEL="${VLLM_MODEL:-$FLOWCEPT_TUTORIAL_MODEL}"
# There is no local/CPU backend on Aurora, so force vLLM unless the user deliberately
# picked another *remote* backend (the Argo escape hatch). An unset value -- or a stale
# `local` left over in the shell/~/.bashrc from a laptop session -- becomes `vllm`;
# only an explicit argo/openai/vllm is honored. (`${VAR:-vllm}` alone would let a
# leftover `local` win and then crash, since local needs a torch we don't use here.)
case "${FLOWCEPT_TUTORIAL_LLM:-}" in
    argo|openai|vllm) : ;;                       # keep a deliberate remote backend
    *) export FLOWCEPT_TUTORIAL_LLM=vllm ;;      # unset / local / anything else -> vLLM
esac

# --- Flowcept: offline (no Redis/Mongo); records -> flowcept_buffer.jsonl --
export FLOWCEPT_SETTINGS_PATH="$REPO/setup/flowcept_settings.yaml"

# --- Serving the model: vLLM on the node's GPUs -----------------------------
# 06/07/08 use an LLM; their submit.pbs bring the server up via
# `source ../vllm_serve.sh && vllm_start` (the same ALCF-staged weights, no network),
# which exports VLLM_BASE_URL so the vLLM default above resolves. There is no CPU
# fallback -- vLLM is the only LLM backend on Aurora. See
# exercises/aurora/README.md ("LLMs on Aurora").
#   * 07 REQUIRES tool calling -- its LangGraph tool_calling node retries a few times
#     and then fails unless the model emits a parseable tool call.
#   * To run query.py's `--ask` you likewise need vLLM up first (same vllm_start); the
#     plain query REPL uses no LLM and needs nothing.
# Escape hatch, if the node reaches the ANL gateway (online, native tool calls):
#         export FLOWCEPT_TUTORIAL_LLM=argo ARGO_USER=<your_anl_username> FLOWCEPT_USE_VLLM=0
# Examples 01-05 use no LLM (03/05 only offload compute) and ignore all of this.

# Exported so each submit.pbs can fall back to `conda run -p "$FLOWCEPT_ENV_PREFIX"`.
export FLOWCEPT_ENV_PREFIX="$ENV_PREFIX"

echo "env ready: conda=$ENV_PREFIX  LLM=vllm(offline staged)  flowcept=offline"
