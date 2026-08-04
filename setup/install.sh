#!/bin/bash -l
# One-command setup for the WHOLE tutorial (all 8 exercises), CPU-only.
# ONE conda env -- no venv, no per-exercise env. Run from the repo root:
#   bash setup/install.sh
#
# Needs conda/miniforge on PATH. On Aurora, `module load frameworks` provides it.
set -euo pipefail

ENV=flowcept-academy
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v conda >/dev/null || { echo "conda not found on PATH; install miniforge or 'module load frameworks'"; exit 1; }
source "$(conda info --base)/etc/profile.d/conda.sh"

# Build the single env (rdkit + xtb for ex 07; agents/LangGraph/LLM for the rest).
if conda env list | grep -qE "^\s*$ENV\s"; then
    echo ">> conda env '$ENV' already exists -- reusing it (delete with: conda env remove -n $ENV)"
else
    conda env create -f "$REPO/setup/environment.yml"
fi

# Install the tutorial library itself into the env.
conda run --no-capture-output -n "$ENV" pip install -e "$REPO"

# Offline Flowcept settings (no Redis/Mongo; records -> flowcept_buffer.jsonl).
mkdir -p "$HOME/.flowcept" && cp "$REPO/setup/flowcept_settings.yaml" "$HOME/.flowcept/settings.yaml"

conda run --no-capture-output -n "$ENV" python -c \
  "from flowcept_academy import util; print('LLM backend:', util.which_backend(), '| local model:', util.DEFAULT_CHAT_MODEL)"

echo ">> Done. Activate:  conda activate $ENV"
echo ">> Start here:      cd exercises/local/01-actor-client && python exercise.py"
echo ">> Reference:       python solution.py   (every provenance step enabled)"
echo ">> LLM example:     cd exercises/local/06-llm && python solution.py"
echo ">> Real chemistry:  cd exercises/local/07-mol-design && python solution.py  (set ARGO_USER first)"
echo ">> Use Argo instead of the local LLM:  export ARGO_USER=<anl-username>"
