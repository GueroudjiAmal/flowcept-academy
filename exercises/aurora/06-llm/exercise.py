"""
EXERCISE 06 -- llm  (LLM-driven ReACT loop calling a tool agent)
================================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped it RUNS but records NO provenance. Uncomment one STEP block at a
    time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    An `Orchestrator` builds a LangChain ReACT agent (`create_agent`) over a tool
    that messages `MySimAgent`. Ask it a question and the LLM decides whether to
    call the `compute_ionization_energy` tool.
      - Academy plugin: lifecycle + the `answer` action and, if the LLM calls the
        tool, the cross-agent `compute_ionization_energy` action.
      - LangGraph callback (langgraph_capture): the ReACT loop's llm_call / tool
        calls -- the LLM reasoning is now first-class provenance.

NOTE (local): upstream builds the LLM with `ChatOpenAI(model, api_key, base_url)`
(an OpenAI-compatible server). The local agent_src swaps in a small local
HuggingFace model (`make_chat_model()`) -- no servers, no keys. On a 0.5B model
the tool call may not always fire; the `answer` action still completes.

Reference: solution.py.  Upstream: academy-agents/academy examples/06-llm/run-06.py
"""
from __future__ import annotations

import asyncio

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from agent_src import MySimAgent, Orchestrator   # <- vendored upstream agents

QUESTION = 'What is the simulated ionization energy of benzene?'


async def run() -> str:
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
    ) as manager:
        simulator = await manager.launch(MySimAgent)
        orchestrator = await manager.launch(
            Orchestrator,
            kwargs={
                'model': 'local',
                'access_token': 'none',
                'simulators': [simulator],
                'base_url': None,
            },
        )
        result = await orchestrator.answer(QUESTION)
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
    print("result:", result)

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # For the ReACT loop's llm_call/tool_call records, wrap the answer() call in
    # langgraph_capture() (see solution.py).
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("06-llm") as run_dir:
    #     # STEP 1 -- CAPTURE (Academy plugin + LangGraph callback)
    #     with captured(workflow_name="06-llm"):
    #         result = asyncio.run(run())
    #     print("result:", result)
    #
    #     # STEP 2 -- INSPECT
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="06-llm -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="06-llm")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/06-llm_*  --ask "which tool did the LLM call?"
    # =====================================================================


if __name__ == "__main__":
    main()
