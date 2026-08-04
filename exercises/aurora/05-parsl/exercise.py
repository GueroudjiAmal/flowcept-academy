"""
EXERCISE 05 -- parsl  (agent delegating to a Parsl task)
========================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py).
    As shipped it RUNS but records NO provenance. Uncomment one STEP block at a
    time in main() and re-run.

HOW TO RUN
    python exercise.py          # STEP 0: baseline (no provenance)

WHAT THE PROVENANCE REVEALS
    A `SimulationAgent` whose `run_expensive_task` action dispatches a REAL Parsl
    `@python_app` (`expensive_task` -> 42).
      - the `academy_action run_expensive_task` record, with `generated=42`.
      - agent lifecycle around the Parsl DFK (startup loads it, shutdown cleans
        it up) -- provenance spans the agent AND the compute backend it drives.

NOTE (local): upstream uses Parsl's HighThroughputExecutor; the local agent_src
uses Parsl's ThreadPoolExecutor (HTEX won't start on a laptop). Same real Parsl
app, different executor -- see agent_src.py.

Reference: solution.py.  Upstream: academy-agents/academy examples/05-parsl/run-05.py
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from academy.exchange.cloud import spawn_http_exchange
from academy.manager import Manager

from agent_src import SimulationAgent   # <- vendored upstream agent, unchanged

EXCHANGE_PORT = 5346


async def run() -> int:
    with spawn_http_exchange('localhost', EXCHANGE_PORT) as factory:
        async with await Manager.from_exchange_factory(
            factory=factory, executors=ThreadPoolExecutor(),
        ) as manager:
            agent = await manager.launch(SimulationAgent)
            result = await agent.run_expensive_task()
            assert result == 42
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
    # with capture_run("05-parsl") as run_dir:
    #     # STEP 1 -- CAPTURE (Flowcept Academy plugin)
    #     with captured(workflow_name="05-parsl"):
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
    #     prov.text_dashboard(df, title="05-parsl -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="05-parsl")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/05-parsl_*  --ask "what did the parsl task return?"
    # =====================================================================


if __name__ == "__main__":
    main()
