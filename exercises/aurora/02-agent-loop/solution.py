"""
SOLUTION 02 -- agent-loop  (autonomous @loop events)
====================================================

Thin, fully-instrumented harness around the vendored upstream agent
(``agent_src.py``, unchanged):

    python solution.py

Upstream: academy-agents/academy  examples/02-agent-loop/run-02.py
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
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
        executors=ThreadPoolExecutor(),
    ) as manager:
        agent = await manager.launch(Counter)

        # Let the autonomous @loop tick a few times, then read the count.
        await asyncio.sleep(2)

        count = await agent.get_count()
        assert count >= 1
        return count


def main() -> None:
    quiet_logging()

    with capture_run("02-agent-loop") as run_dir:
        # STEP 1 -- capture
        with captured(workflow_name="02-agent-loop"):
            result = asyncio.run(run())
        print("loop executed", result, "time(s)")

        # STEP 2 -- inspect
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="02-agent-loop -- provenance")

        # STEP 4 -- card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="02-agent-loop")

    # STEP 5 -- query:  python ../../../provenance/query.py runs/02-agent-loop_*  --ask "..."
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
