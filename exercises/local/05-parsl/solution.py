"""
SOLUTION 05 -- parsl  (agent delegating to a Parsl task)
========================================================

Thin, fully-instrumented harness around the vendored upstream agent
(``agent_src.py``, unchanged). Provenance is collected by the Flowcept agentic
plugin (``FlowceptAcademyPlugin`` via ``captured()``), then analysed + queried:

    python solution.py

The agent runs a REAL Parsl ``@python_app`` (``expensive_task`` -> 42). As in the
upstream example, agents are reached over an HTTP exchange (``spawn_http_exchange``)
so the agent can run its own Parsl DFK in a separate worker process.

Upstream: academy-agents/academy  examples/05-parsl/run-05.py
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from academy.exchange.cloud import spawn_http_exchange
from academy.manager import Manager

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured
from flowcept_academy.util import capture_run, quiet_logging

from agent_src import SimulationAgent

EXCHANGE_PORT = 5346


async def run() -> int:
    """Upstream interaction: launch SimulationAgent, invoke the Parsl-backed action."""
    with spawn_http_exchange('localhost', EXCHANGE_PORT) as factory:
        async with await Manager.from_exchange_factory(
            factory=factory,
            executors=ThreadPoolExecutor(),
        ) as manager:
            agent = await manager.launch(SimulationAgent)
            result = await agent.run_expensive_task()
            assert result == 42
            return result


def main() -> None:
    quiet_logging()

    with capture_run("05-parsl") as run_dir:
        # STEP 1 -- capture provenance with the Flowcept Academy plugin
        with captured(workflow_name="05-parsl"):
            result = asyncio.run(run())
        print("result:", result)

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="05-parsl -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="05-parsl")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/05-parsl_*  --ask "what did run_expensive_task return?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
