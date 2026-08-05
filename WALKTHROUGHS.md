# Example walkthroughs

What each example does, **what its provenance reveals**, and **relevant questions**
to ask the interactive query tool (`provenance/query.py`).

Each example is a step-by-step exercise under `exercises/local/<id>/` (and
`exercises/aurora/<id>/`). Run its `exercise.py` (uncomment one STEP at a time) or
`solution.py` (all steps on); each run lands in `runs/<id>_<date-time>/`, which
you can then query:

```bash
python ../../../provenance/query.py runs/<id>_* --ask "..."
```


## Running these on Aurora

The per-example sections below are **identical on Aurora** — the science, the
provenance graph, and the `ask(...)` questions do not change. What changes is *how you
launch*: a compute-node batch job instead of a local process, and every LLM call goes
to a GPU-served **vLLM** model (ALCF-staged weights, offline) — there is no CPU/local
model on Aurora. Full operational
detail — shared project env, tunables, the one-time vLLM modelinfo-cache fix — is in
[`exercises/aurora/README.md`](exercises/aurora/README.md). The short version:



0. **Clone this repo** — everyone needs their own writable copy (runs land in
   `runs/<id>_<date-time>/` next to the script; the shared *env* below is read-only):

   ```bash
   git clone https://github.com/GueroudjiAmal/flowcept-academy.git
   cd flowcept-academy
   ```

1. **Set up your env.** Two cases:

   **(a) Students — a shared env is already built** (the common case for the tutorial).
   You do **not** run the installer and download nothing. Point at the shared env and
   source `env.sh`:

   ```bash
   export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/agueroudji/envs/flowcept-academy
   # ^ the shared env your instructor built (literal path -- NOT $USER); add to ~/.bashrc
   source exercises/aurora/env.sh
   ```

   **(b) Building it yourself** (one-time, on a login node — login nodes have internet,
   compute nodes do not):

   ```bash
   export FLOWCEPT_ENV_PREFIX=/lus/flare/projects/ATPESC2026/prov/$USER/envs/flowcept-academy
   # ^ add to ~/.bashrc so batch jobs inherit it
   bash setup/install.sh aurora     # clones the frameworks base + delta
   source exercises/aurora/env.sh
   ```

   **Nothing is downloaded** either way. All LLM usage reads ALCF's read-only staged hub at
   `/flare/datasets/model-weights` (`env.sh` points `HF_HOME` there and forces offline),
   so there is no pre-cache and no `chat('hi')` step — do not export your own `HF_HOME`.
   For the LLM examples (06/07/08) `vllm_start` handles the one Aurora quirk for you —
   it primes vLLM's modelinfo cache in-process to dodge the XPU inspection SIGSEGV — see
   *"The XPU model-inspection SIGSEGV"* in the Aurora README.

2. **Submit an example** (`submit.pbs` already has `-A ATPESC2026`):

   ```bash
   cd exercises/aurora/01-actor-client && qsub submit.pbs
   ```

   The job sources `env.sh`, runs `solution.py`, and writes `runs/<id>_<date-time>/`
   (the job's own `job.out`/`job.err` land there too). Backend need per example:
   - **01–05** — no LLM (03/05 just offload compute); nothing to start.
   - **06, 07, 08** — need an LLM; `submit.pbs` starts vLLM on the node's GPUs by
     default. There is no CPU fallback. 07 **requires** tool calling (vLLM provides it).
     Escape hatch if the node reaches Argo:
     `export FLOWCEPT_TUTORIAL_LLM=argo ARGO_USER=... FLOWCEPT_USE_VLLM=0`.

3. **Query the result** — same tool as local, from the example folder. The plain REPL
   needs no LLM; `--ask` does, so start vLLM first (no CPU fallback on Aurora):

   ```bash
   source ../vllm_serve.sh && vllm_start                 # only needed for --ask
   python ../../../provenance/query.py runs/<id>_* --ask "how many tasks are there?"
   ```

**Interactive node** (recommended for stepping through `exercise.py` STEP by STEP, or
iterating on `--ask` queries). Grab a node, then run things by hand — the shared-env
setup is identical, you just source it in the interactive shell:

```bash
qsub -I -A ATPESC2026 -q debug -l select=1 -l walltime=01:00:00 -l filesystems=home:flare
# once you land on the node:
cd exercises/aurora/01-actor-client
source ../env.sh                          # every fresh shell (uses FLOWCEPT_ENV_PREFIX)
source ../vllm_serve.sh && vllm_start     # only for 06/07/08 (they need an LLM)
python solution.py                        # writes runs/<id>_<date-time>/ HERE (all steps on)
vllm_stop                                 # optional; then `exit` to release the node
```

> **No `runs/` after `python exercise.py`?** That's expected: as shipped, `exercise.py`
> is **STEP 0 (baseline) and captures nothing** — the `capture_run(...)`/`captured(...)`
> block is commented out. Run `solution.py` (all steps on) to get a run dir immediately,
> or uncomment **STEP 1** in `exercise.py` first. The dir is created **relative to your
> current directory** (`./runs/…`), so run from inside the example folder. (Batch jobs
> never hit this — `submit.pbs` runs `solution.py` and pre-sets `FLOWCEPT_RUN_DIR`.)

Everything below then applies verbatim; just read `runs/<id>_*` from the compute-node run.


## 01-actor-client  —  agent lifecycle + actions

What it does: launches one stateful `Counter` agent and, from a client, calls its
`@action`s (`get_count`, `increment`, `get_count`). No LLM, no other agents.

What the provenance reveals:
  - agent lifecycle: `academy_lifecycle` startup/shutdown records for the agent.
  - one `academy_action` per call, each with `used` (inputs) and `generated`
    (outputs) -- so you can watch the state evolve: get_count=0 -> increment
    -> get_count=1, every call marked status=FINISHED.
  - the simplest possible capture: this is the baseline the other examples build on.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `how many actions did the agent run?`
  - `what value did each increment produce?`
  - `show the academy_lifecycle events`


## 02-agent-loop  —  autonomous @loop events

What it does: a `Counter` agent with an autonomous `@loop` (`increment`) that
increments itself every second in the background; the client just reads the count.

What the provenance reveals:
  - `academy_loop` records for the loop's **start** and **exit**, sharing a
    `group_id` -- so autonomous behavior is captured distinctly from
    request/response actions.
  - you can see the loop actually ran and when it stopped (at agent shutdown),
    even though nobody "called" it -- provenance captures proactive behavior, not
    just reactive calls.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `how many academy_loop events were captured?`
  - `show the academy_loop records with their loop_event`
  - `which activities are loops versus actions?`


## 03-agent-agent  —  cross-agent calls

What it does: a `Coordinator` delegates to two worker agents -- `Lowerer` then
`Reverser` -- to transform "DEADBEEF" -> "deadbeef" -> "feebdaed".

What the provenance reveals:
  - the data-flow chain across agents via each action's `used`/`generated`.
  - **cross-agent edges**: the `lower`/`reverse` action records carry
    `custom_metadata.cross_agent_call = true` and `source_agent_id` (the
    Coordinator) -- so "who called whom" is reconstructable (the agent-to-agent
    graph), not just what each agent did in isolation.
  - one sub-workflow per agent under the shared campaign.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `show the cross-agent calls`
  - `which agent called which action?`
  - `what did each action transform (used to generated)?`


## 04-execution  —  multi-process execution (make_process_executor)

What it does: a `Distributor` agent runs **in this process** and its `compute`
`@action` offloads a batch of CPU tasks to a pool of **separate worker processes**
built with Flowcept's `make_process_executor`.

What the provenance reveals:
  - the `compute` `academy_action` (captured in-process) with its `used` (the
    batch of sizes) and `generated` -- each result in `generated` records the
    `pid`/`host` it ran on, so the work is shown to **really cross the process
    boundary** (worker pids differ from the main pid and from each other).
  - `make_process_executor` wires every worker for capture and shares the run's
    `campaign_id`/`workflow_id`, so everything stays in one graph.

> Offline note: upstream example 04 runs the *agents themselves* in a process pool
> over an HTTP exchange and aggregates the per-worker records through Flowcept's
> **message queue**. This tutorial is fully offline (no MQ), so it keeps the agent
> in-process and offloads the *compute* to the pool -- same capability, captured
> reliably offline. (There is no `process_task` subtype; the offloaded work's
> location is captured in the `compute` action's `generated` payload.)

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `what pid and host did each result run on?`
  - `how many distinct worker processes ran the compute work?`
  - `show the compute action's used and generated`


## 05-parsl  —  agent delegating to a Parsl task

What it does: a `SimulationAgent` delegates a compute task to **Parsl** (a
`@python_app`) and awaits its result.

What the provenance reveals:
  - the dispatching `academy_action` (`run_expensive_task`) with its `generated`
    result (42) -- the agent -> Parsl hand-off is captured.
  - the pattern that scales in example 07: there, the agent's own process pool runs
    the real xTB chemistry, and each simulation emits a `tool_call` linked back to
    the reasoning node (same `parent_task_id` idea as example 04).

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `what did run_expensive_task generate?`
  - `show the academy_action rows and their generated result`
  - `how many tasks of each subtype are there?`


## 06-llm  —  LLM call + cross-agent tool call

What it does: an `Orchestrator` builds a LangChain ReACT agent (`create_agent`)
over a tool that messages a separate `MySimAgent`; the LLM decides whether to call
the tool to get a simulated energy, then writes the answer. (LLM = Argo →
vLLM → OpenAI → local CPU model, in priority order; on Aurora it's always vLLM.)

What the provenance reveals:
  - `llm_call` tasks linked to their enclosing `@action` (`answer`) via
    `parent_task_id`, with the model used and **token counts** -- you can audit the
    reasoning step.
  - the ReACT graph as `langgraph_graph` + `langgraph_node` records captured by the
    LangChain callback (`langgraph_capture`), sharing the campaign.
  - when the LLM chooses to call the tool, a **cross-agent tool call**
    (Orchestrator -> `MySimAgent.compute_ionization_energy`) ties the reasoning to
    the tool result. (A small local model may answer directly without a tool call;
    a tool-capable backend like Argo exercises the full path.)

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `how many llm_call rows are there and total tokens?`
  - `show the langgraph_node rows`
  - `show the cross-agent calls`


## 07-mol-design  —  cross-framework provenance with REAL GFN2-xTB chemistry

What it does: the upstream Academy `mol-design` agent (vendored unchanged) runs an
LLM reasoning campaign to find molecules with high ionization energy. The campaign
is a LangGraph `StateGraph` (plan -> tool_calling -> simulate -> conclude ->
critique -> update, looping) running inside an Academy `@loop`; the `simulate` step
calls `compute_ionization_energy`, which runs an **actual GFN2-xTB** relaxation
(rdkit builds the geometry, ASE + xtb compute the charged - neutral energy). No
chemistry is mocked. Runs in the shared `flowcept-academy` conda env (the one env
for the whole tutorial, which includes rdkit + ase + xtb); the only extra
requirement is a tool-capable LLM (run with `ARGO_USER` set). This is the single
provenance graph that spans three layers.

What the provenance reveals:
  - **Academy plugin**: the agent lifecycle, the `conduct_simulation_campaign`
    `@loop` (`academy_loop`), each `compute_ionization_energy` call, and `report`.
  - **LangChain callback** (`langgraph_capture`): the reasoning graph
    (`langgraph_graph`) and every node (`langgraph_node`: plan / tool_calling /
    simulate / conclude / critique / update / should_continue), each `llm.ainvoke`
    (`llm_call`, with model + token counts), and each `tool_call` -- all sharing the
    same `campaign_id`, nested under the Academy loop. One graph, three frameworks
    (Academy + LangGraph + xTB), zero edits to the agent.
  - **real results**: each `tool_call` output is a real xTB ionization energy for a
    real (LLM-proposed) molecule; `report` ranks them.
  - if the LLM proposes a molecule whose SMILES xTB can't handle, that
    `compute_ionization_energy` is recorded with `status=ERROR` + `stderr` -- a real,
    not staged, captured failure.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `which molecules were simulated and what were their ionization energies?`
  - `show the langgraph_node rows`
  - `how many tokens did the llm_call rows use in total?`
  - `which tasks have status ERROR and what is the stderr?`


## 08-discussion  —  multi-agent LLM group chat

What it does: a round-robin **LLM group chat** (upstream `group_chat_agents.py`,
vendored unchanged) -- three role-playing `GroupChatAgent`s (Manager, Assistant,
Senior Engineer) take turns via `respond`/`receive`, coordinated by a
`RoundRobinGroupChatManager` that also runs a supervisor `@loop` watching for the
conversation getting stuck. Bounded by `max_rounds` (harness knob).

What the provenance reveals:
  - one `llm_call` per turn (each participant's `respond`, plus the manager's
    stopping / supervisor checks) with the model and **tokens per agent** -- you see
    who spoke and what each contribution cost.
  - the `receive` actions capture the **message fan-out** between agents (each
    agent broadcasts to its peers and the manager), so the dialogue structure is
    queryable.
  - the supervisor `@loop` (`academy_loop`) shows the manager's autonomous
    monitoring running alongside the turn-taking.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `how many llm_call rows are there and total tokens?`
  - `how many actions are receive versus respond?`
  - `show the academy_loop records`

