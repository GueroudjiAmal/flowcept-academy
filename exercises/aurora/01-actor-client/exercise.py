"""
EXERCISE 01 -- actor-client  (agent lifecycle + actions)
========================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped this harness RUNS but records NO provenance. Turn provenance on one
    step at a time: UN-comment each STEP block in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)
    # uncomment STEP 1, re-run; then STEP 2, re-run; ... then STEP 4.

WHAT THE PROVENANCE REVEALS
    Launches one stateful `Counter` agent and calls its `@action`s (`get_count`,
    `increment`, `get_count`). No LLM, no other agents.
      - agent lifecycle: `academy_lifecycle` startup/shutdown records.
      - one `academy_action` per call, each with `used`/`generated` -- watch the
        state evolve get_count=0 -> increment -> get_count=1, all FINISHED.
      - the simplest possible capture: the baseline the other examples build on.

Reference: solution.py (every step already enabled).
Upstream:  academy-agents/academy  examples/01-actor-client/run-01.py
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from agent_src import Counter   # <- vendored upstream agent, unchanged


async def run() -> int:
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(), executors=ThreadPoolExecutor(),
    ) as manager:
        agent = await manager.launch(Counter)
        count = await agent.get_count()
        assert count == 0
        await agent.increment()
        count = await agent.get_count()
        assert count == 1
        return count


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()  # hush library INFO chatter so the report stays readable

    # =====================================================================
    # STEP 0 -- BASELINE. Run the example; print the result. No provenance.
    #   To start capturing: comment the next two lines, then uncomment the
    #   STEP 1-4 block below (reveal inner STEPs 2, 3, 4 one at a time).
    # =====================================================================
    result = asyncio.run(run())
    print("result:", result)

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment this block; every run creates
    #   a fresh  runs/01-actor-client_<date-time>/  holding all the artifacts.
    #   Reveal the inner STEP 2 / 3 / 4 lines one at a time and re-run.
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("01-actor-client") as run_dir:            # -> runs/01-actor-client_<date-time>/
    #     # STEP 1 -- CAPTURE provenance to flowcept_buffer.jsonl (offline)
    #     with captured(workflow_name="01-actor-client"):
    #         result = asyncio.run(run())
    #     print("result:", result)
    #
    #     # STEP 2 -- INSPECT: summary + lineage tree
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE: content-aware analysis + ASCII dashboard
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="01-actor-client -- provenance")
    #
    #     # STEP 4 -- CARD: Flowcept's markdown provenance card
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="01-actor-client")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY it interactively (natural language -> pandas):
    #   python ../../../provenance/query.py runs/01-actor-client_*  --ask "how many actions did the agent run?"
    # =====================================================================


if __name__ == "__main__":
    main()
