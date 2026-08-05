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
# Serve the model's FULL native context so exercise 08 can never overflow it. Llama-3.1-8B
# supports 131072 tokens natively -- that is the real ceiling (going beyond needs RoPE
# scaling, which degrades quality), so 131072 is effectively "unlimited" for this tutorial.
# Why this matters: 08's group chat accumulates the WHOLE discussion and the `supervize`
# loop re-sends it every round, so its context grows with the conversation and kept grazing
# smaller ceilings -- 8192 overflowed (8195 tokens), then 32768 overflowed by a hair (32771).
# At 131072 there is 4x the headroom of that failure. KV cache scales with this (Llama-3.1-8B
# ~128 KB/token -> ~16 GB for a full 131072-token sequence), which still fits a 64GB tile
# alongside the ~16 GB of weights. vLLM reserves KV blocks for one max-length sequence at
# startup; if a memory-tight node ever fails to launch, drop this to 65536.
export VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-131072}"
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

# vLLM's modelinfo cache. On Aurora's XPU, vLLM's serve-time model-architecture
# inspection spawns a helper subprocess that SEGFAULTs (SIGSEGV) -- serve then dies
# with "Model architectures ['LlamaForCausalLM'] failed to be inspected / validation
# error for ModelConfig". The fix (ALCF frameworks-sdk, dir literally named
# "xpu-model-inspection-hidden-sigsegv") is to build the modelinfo cache IN-PROCESS
# once -- which never spawns the crashing subprocess -- and let serve reuse it.
# vllm_start does this automatically via _vllm_prime_cache() below (vendored under
# vllm_wa/), using THIS VLLM_CACHE_ROOT for both prime and serve. Point it at project
# space for a shared group setup so everyone reuses one populated cache; it must be
# WRITABLE (unlike HF_HOME, which is the read-only staged hub).
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-$HOME/.cache/vllm}"

_VLLM_PID=""
_VLLM_LOG=""

# Point the tutorial at the vLLM endpoint. flowcept_academy.util sees VLLM_BASE_URL and
# builds a ChatOpenAI against it -- the same code path as Argo/OpenAI. Call this in EVERY
# shell that will talk to vLLM (agents or query.py --ask): the exports live in the shell
# that runs them, so a second shell needs its own `source ../vllm_serve.sh && vllm_start`
# (which adopts an already-running server and re-exports these).
_vllm_export_env() {
    export FLOWCEPT_TUTORIAL_LLM=vllm
    export VLLM_BASE_URL="http://localhost:$VLLM_PORT/v1"
    export OPENAI_API_KEY=EMPTY
    unset ARGO_USER            # else it would win the routing in which_backend()
}

# The frameworks Python that owns the `vllm` binary (NOT the tutorial env's python,
# which has no vllm). `vllm` is a console script; its shebang is that interpreter.
_vllm_python() {
    local bin py
    bin="$(command -v vllm 2>/dev/null)" || return 1
    py="$(sed -n '1s/^#!//p' "$bin" 2>/dev/null)"
    [[ -x "$py" ]] || py="$(dirname "$bin")/python3.12"
    [[ -x "$py" ]] || py="$(dirname "$bin")/python"
    [[ -x "$py" ]] || return 1
    printf '%s\n' "$py"
}

# ALCF workaround for the XPU model-inspection SIGSEGV (see the VLLM_CACHE_ROOT note
# above). Build the served model's modelinfo cache IN-PROCESS with the frameworks
# python -- this loads the model CLASS (no weights, seconds) without spawning the
# subprocess that crashes -- so the subsequent `vllm serve` gets a cache hit and skips
# inspection entirely. Idempotent: re-priming an already-cached arch is cheap and
# harmless. Never fatal -- if it can't prime, serve is still attempted.
_vllm_prime_cache() {
    local py builder wa_dir arch
    py="$(_vllm_python)" || { echo ">> (no frameworks python found; skipping cache prime)"; return 0; }
    wa_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vllm_wa"
    builder="$wa_dir/vllm_build_all_modelinfo_caches.py"
    [[ -f "$builder" ]] || { echo ">> (cache primer missing at $builder; skipping)"; return 0; }

    mkdir -p "$VLLM_CACHE_ROOT" 2>/dev/null || true

    # Which architecture does the served model use? Read it offline from the staged
    # config (HF_HOME + HF_HUB_OFFLINE already point at the read-only hub).
    arch="$("$py" - "$VLLM_MODEL" <<'PY' 2>/dev/null
import sys
try:
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(sys.argv[1])
    archs = getattr(cfg, "architectures", None) or []
    print(archs[0] if archs else "")
except Exception:
    print("")
PY
)" || arch=""

    echo ">> priming vLLM modelinfo cache (avoids the XPU inspection SIGSEGV)"
    echo ">>   VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT${arch:+  arch=$arch}"
    if [[ -n "$arch" ]]; then
        VLLM_CACHE_ROOT="$VLLM_CACHE_ROOT" "$py" "$builder" --arch "$arch" \
            || echo ">> (prime for $arch returned nonzero; serve will still be tried)"
    else
        # Couldn't resolve the arch; build the whole registry (slower but safe).
        echo ">>   (arch unknown; building all registry entries)"
        VLLM_CACHE_ROOT="$VLLM_CACHE_ROOT" "$py" "$builder" \
            || echo ">> (prime returned nonzero; serve will still be tried)"
    fi
}

vllm_start() {
    # vLLM lives in the frameworks module base (/opt/aurora/.../bin/vllm), NOT in the
    # tutorial conda env. If activating the tutorial env shadowed it (or the module
    # isn't loaded), recover it from the module before giving up. Drop nounset around
    # the module calls (Lmod derefs $ZSH_EVAL_CONTEXT, fatal under set -u).
    if ! command -v vllm >/dev/null; then
        _vllm_had_u=0; case $- in *u*) _vllm_had_u=1;; esac
        set +u
        module use /soft/modulefiles 2>/dev/null || true
        module load frameworks 2>/dev/null || true
        [[ $_vllm_had_u == 1 ]] && set -u; unset _vllm_had_u
    fi
    command -v vllm >/dev/null || {
        echo "!! vllm not found. vLLM ships in the ALCF 'frameworks' module and needs the"
        echo "!! GPUs, so this only works on an AURORA COMPUTE NODE (qsub -I ... or inside"
        echo "!! a batch job), after 'module load frameworks'. On a login node or laptop"
        echo "!! there is no vllm -- use the exercises/local/ CPU path there instead."
        return 1
    }

    # If a vLLM is ALREADY answering on this port (e.g. you started it in another shell,
    # or the batch job left it up), don't start a second server -- adopt it: just export
    # the routing env into THIS shell and return. This is what makes
    # `source ../vllm_serve.sh && vllm_start` work in a fresh shell for `query.py --ask`.
    # (If it's the wrong server, set VLLM_PORT to a free port or kill the stale one.)
    if curl -s -o /dev/null -m 2 "http://localhost:$VLLM_PORT/v1/models"; then
        echo ">> vLLM already answering on port $VLLM_PORT -- adopting it (not starting a second server)."
        _vllm_export_env
        echo ">> routed: FLOWCEPT_TUTORIAL_LLM=vllm  VLLM_BASE_URL=$VLLM_BASE_URL"
        return 0
    fi

    # Populate the modelinfo cache in-process FIRST, or serve segfaults on XPU.
    _vllm_prime_cache

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
            echo "!! If this is 'failed to be inspected' / 'validation error for ModelConfig',"
            echo "!! the modelinfo cache under VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT is missing this"
            echo "!! model's arch. Prime it by hand (uses the frameworks python):"
            echo "!!   VLLM_CACHE_ROOT=$VLLM_CACHE_ROOT \\"
            echo "!!     \$(sed -n '1s/^#!//p' \"\$(command -v vllm)\") \\"
            echo "!!     $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vllm_wa/vllm_build_all_modelinfo_caches.py --arch LlamaForCausalLM"
            echo "!! See exercises/aurora/README.md (\"the XPU model-inspection SIGSEGV\")."
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

    # Route this shell at it (same code path as Argo/OpenAI).
    _vllm_export_env
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

# --- On source: adopt an already-running server -----------------------------
# So that just `source ../env.sh && source ../vllm_serve.sh` gives a fresh shell
# EVERYTHING it needs (VLLM_BASE_URL etc.) when a vLLM is already up on this node --
# e.g. a second shell for `query.py --ask` while a job/other shell serves the model.
# No server yet? This is a no-op; the config vars + functions are defined, so the
# normal `vllm_start` flow (prime cache -> serve -> export) still works. Never fatal.
if curl -s -o /dev/null -m 2 "http://localhost:$VLLM_PORT/v1/models" 2>/dev/null; then
    _vllm_export_env
    echo ">> vLLM already up on port $VLLM_PORT -- routed this shell (VLLM_BASE_URL=$VLLM_BASE_URL)."
    echo ">> (no need to run vllm_start here; use it only to LAUNCH a server.)"
else
    echo ">> vllm_serve.sh loaded. No server on port $VLLM_PORT yet -- run 'vllm_start' to launch one."
fi
