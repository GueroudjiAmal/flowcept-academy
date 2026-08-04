"""
SOLUTION 03 -- agent-agent  (multi-agent delegation)
====================================================

Thin, fully-instrumented harness around the vendored upstream agents
(``agent_src.py``, unchanged). Provenance is collected by the Flowcept agentic
plugin (``FlowceptAcademyPlugin`` via ``captured()``), then analysed + queried:

    python solution.py

Upstream: academy-agents/academy  examples/03-agent-agent/run-03.py
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

from agent_src import Coordinator, Lowerer, Reverser


async def run() -> str:
    """Upstream interaction: Coordinator delegates to Lowerer then Reverser."""
    async with await Manager.from_exchange_factory(
        factory=LocalExchangeFactory(),
        executors=ThreadPoolExecutor(),
    ) as manager:
        lowerer = await manager.launch(Lowerer)
        reverser = await manager.launch(Reverser)
        coordinator = await manager.launch(Coordinator, args=(lowerer, reverser))

        text = 'DEADBEEF'
        expected = 'feebdaed'
        result = await coordinator.process(text)
        assert result == expected
        return result


def main() -> None:
    quiet_logging()

    with capture_run("03-agent-agent") as run_dir:
        # STEP 1 -- capture provenance with the Flowcept Academy plugin
        with captured(workflow_name="03-agent-agent"):
            result = asyncio.run(run())
        print("result:", result)

        # STEP 2 -- inspect: summary + lineage across the 3 agents
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="03-agent-agent -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="03-agent-agent")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/03-agent-agent_*  --ask "which agent lowered the text?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
