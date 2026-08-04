"""
SOLUTION 04 -- execution  (multi-PROCESS execution via make_process_executor)
=============================================================================

Thin, fully-instrumented harness around ``agent_src.py``. A single ``Distributor``
agent runs **in this process** (so the Flowcept Academy plugin captures its
lifecycle and its ``@action``) and its ``compute`` action offloads the heavy work
to a pool of **separate worker processes** built with Flowcept's
``make_process_executor``.

    python solution.py

The key piece is ``make_process_executor()`` (a Flowcept plugin API): it builds a
``ProcessPoolExecutor`` whose every worker process is pre-wired for provenance
capture and shares the run's ``workflow_id``/``campaign_id``. The work really runs
in separate OS processes -- each result records the ``pid``/``host`` it ran on --
so the captured ``compute`` action's ``generated`` payload proves the computation
crossed the process boundary.

Note on offline mode (why this differs from upstream run-04.py): upstream runs the
agents *themselves* in the pool over an HTTP exchange and relies on Flowcept's
message queue to aggregate per-worker records. This tutorial runs fully offline
(no MQ), where worker-process records cannot be flushed back, so example 04 keeps
the agent in-process and offloads the *compute* to the pool -- same capability,
captured reliably offline. See agent_src.py for the full rationale.

Upstream: academy-agents/academy  examples/04-execution/run-04.py
"""
from __future__ import annotations

import asyncio
import os

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from flowcept.agents.academy.academy_plugin import make_process_executor

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured
from flowcept_academy.util import capture_run, quiet_logging

from agent_src import Distributor, set_executor

# How much work to fan out: one unit per worker process (each ~n*50k iterations).
SIZES = [2, 3, 4, 5, 6]


async def run() -> list:
    """The agent runs in-process; its action offloads work to separate processes."""
    # make_process_executor() must be called while the Academy plugin is active
    # (we are inside captured()); every worker is then wired for capture and
    # shares this run's workflow_id / campaign_id.
    executor = make_process_executor(max_workers=3)
    set_executor(executor)
    try:
        async with await Manager.from_exchange_factory(
            factory=LocalExchangeFactory(),
        ) as manager:
            agent = await manager.launch(Distributor)
            results = await agent.compute(SIZES)
            return results
    finally:
        executor.shutdown(wait=True)


def main() -> None:
    quiet_logging()

    with capture_run("04-execution") as run_dir:
        # STEP 1 -- capture provenance (Academy plugin + per-worker interceptors)
        with captured(workflow_name="04-execution"):
            results = asyncio.run(run())
        pids = sorted({r["pid"] for r in results})
        print(f"result: {len(results)} tasks ran across {len(pids)} worker processes "
              f"(pids {pids}); main pid {os.getpid()}")

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="04-execution -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="04-execution")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/04-execution_*  --ask "what pid and host did each result run on?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
