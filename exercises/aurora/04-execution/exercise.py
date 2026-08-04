"""
EXERCISE 04 -- execution  (multi-PROCESS execution via make_process_executor)
=============================================================================

WHAT THIS IS
    A ``Distributor`` agent (agent_src.py) whose ``@action`` offloads CPU work to
    a pool of SEPARATE worker processes. As shipped it RUNS but records NO
    provenance. Uncomment one STEP block at a time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    The agent runs in THIS process (so the Academy plugin captures its lifecycle
    and its ``compute`` action), and the action offloads work to SEPARATE
    PROCESSES via `make_process_executor()` (a Flowcept plugin API):
      - `make_process_executor()` builds a ProcessPoolExecutor whose workers are
        pre-wired for capture and share the run's workflow_id/campaign_id.
      - the work really runs in other OS processes -- each result records the
        pid/host it ran on, so the captured `compute` action's `generated`
        payload proves the computation crossed the process boundary.

    (Offline note: upstream example 04 runs the agents *themselves* in the pool
    and aggregates worker records via Flowcept's message queue. This tutorial is
    offline -- no MQ -- so it keeps the agent in-process and offloads the compute;
    same capability, captured reliably offline. See agent_src.py.)

Reference: solution.py.  Upstream: academy-agents/academy examples/04-execution/run-04.py
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from agent_src import Distributor, set_executor   # <- the offloading agent

SIZES = [2, 3, 4, 5, 6]


async def run() -> list:
    # STEP 0 baseline: a plain ProcessPoolExecutor (no provenance yet). When you
    # switch on capture below, swap this for make_process_executor() so the worker
    # processes are instrumented too (see solution.py).
    executor = ProcessPoolExecutor(max_workers=3)
    set_executor(executor)
    try:
        async with await Manager.from_exchange_factory(
            factory=LocalExchangeFactory(),
        ) as manager:
            agent = await manager.launch(Distributor)
            return await agent.compute(SIZES)
    finally:
        executor.shutdown(wait=True)


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()

    # =====================================================================
    # STEP 0 -- BASELINE. No provenance.
    # =====================================================================
    results = asyncio.run(run())
    pids = sorted({r["pid"] for r in results})
    print(f"result: {len(results)} tasks across {len(pids)} worker processes (pids {pids})")

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # NOTE: for capture-wired workers, replace the ProcessPoolExecutor in run()
    # with make_process_executor() (see solution.py). make_process_executor()
    # must be called inside captured().
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("04-execution") as run_dir:
    #     # STEP 1 -- CAPTURE (Academy plugin + per-worker interceptors)
    #     with captured(workflow_name="04-execution"):
    #         results = asyncio.run(run())
    #     pids = sorted({r["pid"] for r in results})
    #     print(f"result: {len(results)} tasks across {len(pids)} worker processes")
    #
    #     # STEP 2 -- INSPECT
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="04-execution -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="04-execution")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/04-execution_*  --ask "what pid and host did each result run on?"
    # =====================================================================


if __name__ == "__main__":
    main()
