"""
EXERCISE 02 -- agent-loop  (autonomous @loop events)
====================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped it RUNS but records NO provenance. Uncomment one STEP block at a
    time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    A `Counter` agent with an autonomous `@loop` (`increment`) that ticks every
    second in the background; the client just reads the count.
      - `academy_loop` records for the loop's start and exit (shared `group_id`)
        -- autonomous behavior captured distinctly from request/response actions.
      - you can see the loop actually ran and when it stopped (at shutdown), even
        though nobody "called" it: provenance captures proactive behavior too.

Reference: solution.py.  Upstream: academy-agents/academy examples/02-agent-loop/run-02.py
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
        await asyncio.sleep(10)          # let the @loop tick
        count = await agent.get_count()
        assert count >= 1
        return count


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()

    # =====================================================================
    # STEP 0 -- BASELINE. No provenance.
    # =====================================================================
    result = asyncio.run(run())
    print("loop executed", result, "time(s)")

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("02-agent-loop") as run_dir:
    #     # STEP 1 -- CAPTURE
    #     with captured(workflow_name="02-agent-loop"):
    #         result = asyncio.run(run())
    #     print("loop executed", result, "time(s)")
    #
    #     # STEP 2 -- INSPECT
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="02-agent-loop -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="02-agent-loop")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/02-agent-loop_*  --ask "how many academy_loop events were captured?"
    # =====================================================================


if __name__ == "__main__":
    main()
