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


## 01-actor-client  —  agent lifecycle + actions

What it does: launches one stateful `Counter` agent and, from a client, calls its
`@action`s (`increment`, `increment(10)`, `get_count`). No LLM, no other agents.

What the provenance reveals:
  - agent lifecycle: `academy_lifecycle` startup/shutdown records for the agent.
  - one `academy_action` per call, each with `used` (inputs) and `generated`
    (outputs) -- so you can watch the state evolve: increment -> increment(10)
    -> get_count = 11, every call marked status=FINISHED.
  - the simplest possible capture: this is the baseline the other examples build on.

**Ask the query tool** (`python ../../../provenance/query.py runs/<id>_* --ask "..."`):
  - `how many actions did the agent run?`
  - `what value did each increment produce?`
  - `show the academy_lifecycle events`


## 02-agent-loop  —  autonomous @loop events

What it does: a `Counter` agent with an autonomous `@loop` (`ticker`) that
increments itself every 0.5s in the background; the client just reads the count.

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
OpenAI → local CPU model, in priority order.)

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

