# Source this on Aurora before running ANY exercise:  source ../env.sh
# It is also sourced by every exercise's submit.pbs (all 8, including 07).
#
# ONE conda env (flowcept-academy) for the whole tutorial -- built once on a login
# node by setup/install.sh. Sets up: ALCF frameworks module, the conda env, an
# OFFLINE local CPU LLM (no Argo needed on compute nodes), and Flowcept's offline
# settings.

# Repo root = two levels up from exercises/aurora/
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV=flowcept-academy

# --- ALCF modules (provide conda) ------------------------------------------
module use /soft/modulefiles 2>/dev/null || true
module load frameworks 2>/dev/null || true

# --- The single conda env (built once by setup/install.sh) -----------------
# 'conda activate' needs conda's shell hook; submit.pbs falls back to `conda run`
# if activation doesn't take in a non-interactive job.
source "$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate "$ENV" 2>/dev/null || true

# --- LLM: local CPU model, fully offline -----------------------------------
# Pre-cache the model on a login node first (has internet):
#   python -c "from flowcept_academy.util import chat; print(chat('hi'))"
# then compute nodes read it from HF_HOME with HF_HUB_OFFLINE=1.
export HF_HOME="$REPO/hf_cache"
export HF_HUB_OFFLINE=1
export FLOWCEPT_TUTORIAL_LLM=local

# --- Flowcept: offline (no Redis/Mongo); records -> flowcept_buffer.jsonl --
export FLOWCEPT_SETTINGS_PATH="$REPO/setup/flowcept_settings.yaml"

# --- Exercise 07 ONLY needs a tool-capable LLM -----------------------------
# 07's LangGraph tool_calling node retries until the model emits a parseable tool
# call. The default local 0.5B model does NOT emit tool calls, so BEFORE running 07
# pick one of:
#   (a) Argo (native tool calling), if the compute node reaches the ANL gateway:
#         export ARGO_USER=<your_anl_username>
#   (b) a tool-capable local model, offline (pre-cache it on a login node first):
#         export FLOWCEPT_TUTORIAL_MODEL=Qwen/Qwen2.5-7B-Instruct
# Examples 01-06/08 run fine on the default 0.5B model above.

echo "env ready: conda=$ENV  LLM=local(offline)  flowcept=offline"
