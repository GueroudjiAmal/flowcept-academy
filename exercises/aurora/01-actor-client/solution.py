"""
SOLUTION 01 -- actor-client  (agent lifecycle + actions)
========================================================

Thin, fully-instrumented harness around the vendored upstream agent
(``agent_src.py``, unchanged). capture -> inspect -> analyze -> card, all on:

    python solution.py

Upstream: academy-agents/academy  examples/01-actor-client/run-01.py
"""
from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured
from flowcept_academy.util import capture_run, quiet_logging

from agent_src import Counter


async def run() -> int:
    """Upstream interaction, run on a local exchange + thread executor (CPU-friendly)."""
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
        executors=ThreadPoolExecutor(),
    ) as manager:
        agent = await manager.launch(Counter)

        count = await agent.get_count()
        assert count == 0

        await agent.increment()

        count = await agent.get_count()
        assert count == 1
        return count


def main() -> None:
    quiet_logging()

    # Each run lands in its own  runs/01-actor-client_<date-time>/  (buffer, perf CSV, card).
    with capture_run("01-actor-client") as run_dir:
        # STEP 1 -- capture provenance to flowcept_buffer.jsonl
        with captured(workflow_name="01-actor-client"):
            result = asyncio.run(run())
        print("result:", result)

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="01-actor-client -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="01-actor-client")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/01-actor-client_*  --ask "..."
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
