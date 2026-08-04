"""
EXERCISE 08 -- discussion  (multi-agent LLM group chat)
=======================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped it RUNS but records NO provenance. Uncomment one STEP block at a
    time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    Three role-playing `GroupChatAgent`s (Manager / Assistant / Senior Engineer)
    take turns in a round-robin driven by a `RoundRobinGroupChatManager`, which
    also runs a supervisor `@loop` that watches for the conversation getting stuck.
      - Academy plugin: lifecycle for all 4 agents, every `respond` / `receive` /
        `query` action, and the `supervize` loop.
      - LangChain callback (langgraph_capture): every `llm.ainvoke(...)` -- each
        participant's turn plus the stopping / supervisor checks -- as an
        `llm_call`. The whole multi-agent discussion becomes one provenance graph.

NOTE (local): upstream builds the LLM with `ChatOpenAI(model=...)` (a hosted 17B
model) and `max_rounds=10`. The local harness injects a small local HuggingFace
model (`make_chat_model()`) and bounds `max_rounds` so the run stays tractable on
CPU -- the agent logic is byte-for-byte upstream (the LLM is a constructor arg).

Reference: solution.py.  Upstream: academy-agents/academy examples/08-discussion/
"""
from __future__ import annotations

import asyncio

from academy.exchange import LocalExchangeFactory
from academy.handle import Handle
from academy.manager import Manager

from agent_src import GroupChatAgent, RoundRobinGroupChatManager  # <- vendored upstream
from flowcept_academy.util import make_chat_model

QUESTION = (
    'What size parachute do I need to stop a 10kg plastic rocket from'
    " breaking when it's launched 300ft"
)
MAX_ROUNDS = 2   # harness knob; upstream uses 10 against a hosted 17B model


def _build_agents(llm):
    return [
        GroupChatAgent(llm, role='Manager', prompt=(
            'Your are managing a team. Participate in the conversation with a '
            'user by coming up with subtasks for your team to solve. Your team '
            'consists of a junior assistant and a senior engineer.')),
        GroupChatAgent(llm, role='Assistant', prompt=(
            'You are an assistant. Participate in the conversation by taking '
            'care of small or trivial tasks needed to complete the users '
            'request. Purposely make mistakes and repeat calculations to get '
            'the conversation stuck.')),
        GroupChatAgent(llm, role='Senior Engineer', prompt=(
            'You are a senior enginner. Participate in the conversation by '
            'assessing the Assistants results and checking them for accuracy.')),
    ]


async def run() -> str:
    llm = make_chat_model(max_new_tokens=128)
    agents = _build_agents(llm)
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
    ) as manager:
        participants: list[Handle[GroupChatAgent]] = []
        for agent in agents:
            participants.append(await manager.launch(agent))
        supervisor = await manager.launch(
            RoundRobinGroupChatManager,
            kwargs={'participants': participants, 'llm': llm, 'max_rounds': MAX_ROUNDS},
        )
        result = await supervisor.query(QUESTION)
        return str(result)


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()

    # =====================================================================
    # STEP 0 -- BASELINE. No provenance.
    # =====================================================================
    print(QUESTION)
    result = asyncio.run(run())
    print("last message:", result)

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # For per-call llm_call records, wrap run() in langgraph_capture() (see
    # solution.py) and enter it BEFORE launching the agents.
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("08-discussion") as run_dir:
    #     # STEP 1 -- CAPTURE (Academy plugin + LangChain callback)
    #     with captured(workflow_name="08-discussion"):
    #         result = asyncio.run(run())
    #     print("last message:", result)
    #
    #     # STEP 2 -- INSPECT
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="08-discussion -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="08-discussion")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/08-discussion_*  --ask "how many LLM calls, by which role?"
    # =====================================================================


if __name__ == "__main__":
    main()
