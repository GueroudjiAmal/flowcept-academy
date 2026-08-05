# Start a vLLM server on THIS Aurora compute node and point the tutorial at it.
#
#   source ../vllm_serve.sh
#   vllm_start                 # blocks until the server answers, then exports the env
#   python solution.py
#   vllm_stop                  # (also runs automatically on job exit)
#
# Why: Aurora compute nodes reach neither Argo nor api.openai.com, and the offline
# CPU fallback (the staged model via transformers) cannot emit tool calls -- which
# example 07 requires. vLLM ships in the ALCF `frameworks` module and serves models straight
# off /flare/datasets/model-weights, so we get a real tool-capable model with no
# external network at all. It talks the OpenAI API, so flowcept_academy.util routes
# to it through the same ChatOpenAI path Argo/OpenAI use -- agent code unchanged.
#
# Cost: ~2-5 min of startup and one GPU tile per job. Examples 01-05 barely touch the
# LLM, so they stay on the CPU model; this is for 06/07/08.

# --- What to serve ----------------------------------------------------------
# Default to a model ALCF pre-stages under /flare/datasets/model-weights (see the
# ALCF Aurora vLLM docs) so nothing is ever downloaded. A PVC tile is 64 GB, so
# anything under ~20B in bfloat16 fits with TP=1. The tool-call parser is
# model-family specific and MUST match, or the server will happily generate text
# that never parses as a tool call (07 would retry a few times, then fail):
#
#   meta-llama/Llama-3.1-8B-Instruct    --tool-call-parser llama3_json   (default; ALCF-staged)
#   meta-llama/Llama-3.3-70B-Instruct   --tool-call-parser llama3_json   (needs more tiles, raise VLLM_TP)
#   Qwen/Qwen2.5-7B-Instruct            --tool-call-parser hermes        (only if staged)
#
export VLLM_MODEL="${VLLM_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
export VLLM_TOOL_PARSER="${VLLM_TOOL_PARSER:-llama3_json}"
export VLLM_PORT="${VLLM_PORT:-8000}"
export VLLM_TP="${VLLM_TP:-1}"              # tiles; 1 is enough under ~20B
export VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-8192}"
export VLLM_STARTUP_TIMEOUT="${VLLM_STARTUP_TIMEOUT:-900}"   # seconds

# --- Weights: ALCF's pre-staged hub, read-only, no download ------------------
# Overrides the tutorial's own HF_HOME (set by env.sh) for the served model.
export HF_HOME="${VLLM_HF_HOME:-/flare/datasets/model-weights}"
export HF_DATASETS_CACHE="$HF_HOME"
export HF_MODULES_CACHE="$HF_HOME"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export RAY_TMPDIR="${RAY_TMPDIR:-/tmp}"
export TMPDIR="${TMPDIR:-/tmp}"
export no_proxy="localhost,127.0.0.1${no_proxy:+,$no_proxy}"

# vLLM's modelinfo cache. Must be pre-populated ONCE from a node with proxies (see
# exercises/aurora/README.md); an empty cache makes the server die at startup with
# "validation error for ModelConfig". For a shared group setup, point this at the
# same project space as FLOWCEPT_ENV_PREFIX so everyone reuses one populated cache.
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-$HOME/.cache/vllm}"

_VLLM_PID=""
_VLLM_LOG=""

vllm_start() {
    command -v vllm >/dev/null || {
        echo "!! vllm not found -- is the ALCF frameworks module loaded? (source ../env.sh)"
        return 1
    }

    # Refuse to start if something already answers on the port -- otherwise the
    # readiness probe below would pass instantly against the wrong server (a stale
    # vLLM from a previous run, say) and every request would go to it.
    if curl -s -o /dev/null -m 2 "http://localhost:$VLLM_PORT/v1/models"; then
        echo "!! something is already listening on port $VLLM_PORT."
        echo "!! Set VLLM_PORT to a free port, or kill the stale server first."
        return 1
    fi

    _VLLM_LOG="${PWD}/vllm_server.log"
    echo ">> starting vLLM: $VLLM_MODEL (TP=$VLLM_TP, port=$VLLM_PORT)"
    echo ">> log: $_VLLM_LOG"

    vllm serve "$VLLM_MODEL" \
        --port "$VLLM_PORT" \
        --tensor-parallel-size "$VLLM_TP" \
        --max-model-len "$VLLM_MAX_MODEL_LEN" \
        --dtype bfloat16 \
        --enforce-eager \
        --enable-auto-tool-choice \
        --tool-call-parser "$VLLM_TOOL_PARSER" \
        > "$_VLLM_LOG" 2>&1 &
    _VLLM_PID=$!

    # Kill the server even if the job script dies or is cancelled.
    trap vllm_stop EXIT INT TERM

    # Wait for "Application startup complete." -- i.e. /v1/models answers.
    local waited=0
    until curl -s -o /dev/null "http://localhost:$VLLM_PORT/v1/models"; do
        if ! kill -0 "$_VLLM_PID" 2>/dev/null; then
            echo "!! vLLM died during startup. Last 40 lines of $_VLLM_LOG:"
            tail -40 "$_VLLM_LOG"
            echo "!! If this is 'validation error for ModelConfig', the VLLM_CACHE_ROOT"
            echo "!! modelinfo cache was never populated -- see exercises/aurora/README.md."
            return 1
        fi
        if (( waited >= VLLM_STARTUP_TIMEOUT )); then
            echo "!! vLLM did not come up within ${VLLM_STARTUP_TIMEOUT}s; last 40 lines:"
            tail -40 "$_VLLM_LOG"
            vllm_stop
            return 1
        fi
        sleep 5
        waited=$((waited + 5))
    done
    echo ">> vLLM ready after ${waited}s"

    # Route the tutorial at it. flowcept_academy.util sees VLLM_BASE_URL and builds
    # a ChatOpenAI against this endpoint -- same code path as Argo/OpenAI.
    export FLOWCEPT_TUTORIAL_LLM=vllm
    export VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1"
    export OPENAI_API_KEY=EMPTY
    unset ARGO_USER            # else it would win the routing in which_backend()
}

# Signal a process and all its descendants, children first. vLLM forks engine
# workers, and killing only the parent leaves them holding the GPU tile for the rest
# of the job. We walk the tree explicitly rather than using a process-group kill:
# background jobs in a non-interactive shell share the *shell's* group, so
# `kill -- -$pid` could take out the PBS job script itself.
_vllm_kill_tree() {
    local pid=$1 sig=$2 kid
    for kid in $(pgrep -P "$pid" 2>/dev/null); do
        _vllm_kill_tree "$kid" "$sig"
    done
    kill "-$sig" "$pid" 2>/dev/null || true
}

vllm_stop() {
    trap - EXIT INT TERM
    [[ -n "$_VLLM_PID" ]] || return 0
    kill -0 "$_VLLM_PID" 2>/dev/null || { _VLLM_PID=""; return 0; }
    echo ">> stopping vLLM (pid $_VLLM_PID)"
    _vllm_kill_tree "$_VLLM_PID" TERM
    # Give it 20s to release the GPU, then insist.
    local waited=0
    while kill -0 "$_VLLM_PID" 2>/dev/null && (( waited < 20 )); do
        sleep 1; waited=$((waited + 1))
    done
    if kill -0 "$_VLLM_PID" 2>/dev/null; then
        echo ">> vLLM did not exit in ${waited}s; sending KILL"
        _vllm_kill_tree "$_VLLM_PID" KILL
    fi
    wait "$_VLLM_PID" 2>/dev/null || true
    _VLLM_PID=""
}
