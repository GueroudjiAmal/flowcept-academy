"""
EXERCISE 03 -- agent-agent  (multi-agent delegation)
====================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped it RUNS but records NO provenance. Uncomment one STEP block at a
    time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    Three agents: a `Coordinator` that delegates to a `Lowerer` and a `Reverser`
    to transform "DEADBEEF" -> "feebdaed".
      - one `academy_action` per call, spread across THREE agents (watch the
        `by agent` breakdown).
      - nested lineage: `Coordinator.process` is the parent; `lower` and
        `reverse` are the child calls it made -- delegation captured as structure.

Reference: solution.py.  Upstream: academy-agents/academy examples/03-agent-agent/run-03.py
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from agent_src import Coordinator, Lowerer, Reverser   # <- vendored upstream agents, unchanged


async def run() -> str:
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(), executors=ThreadPoolExecutor(),
    ) as manager:
        lowerer = await manager.launch(Lowerer)
        reverser = await manager.launch(Reverser)
        coordinator = await manager.launch(Coordinator, args=(lowerer, reverser))
        result = await coordinator.process('DEADBEEF')
        assert result == 'feebdaed'
        return result


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()

    # =====================================================================
    # STEP 0 -- BASELINE. No provenance.
    # =====================================================================
    result = asyncio.run(run())
    print("result:", result)

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("03-agent-agent") as run_dir:
    #     # STEP 1 -- CAPTURE (Flowcept Academy plugin)
    #     with captured(workflow_name="03-agent-agent"):
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
    #     prov.text_dashboard(df, title="03-agent-agent -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="03-agent-agent")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/03-agent-agent_*  --ask "which agent reversed the text?"
    # =====================================================================


if __name__ == "__main__":
    main()
