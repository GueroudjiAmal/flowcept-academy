"""Vendored VERBATIM from the upstream Academy example (agent logic only).

Source: academy-agents/academy  examples/05-parsl/run-05.py
        https://github.com/academy-agents/academy/blob/main/examples/05-parsl/run-05.py

Only the Parsl app + agent class are vendored here, unchanged -- the run harness
lives in solution.py / exercise.py so the Flowcept plugins wrap this code without
editing it.

LOCAL-ONLY EXECUTOR SWAP
------------------------
Upstream uses ``parsl.HighThroughputExecutor`` (HTEX), which spins up an
interchange process + worker pool over local ports. That does not start on a
plain laptop (it hangs in ``parsl.load``), so the LOCAL copy uses Parsl's
``ThreadPoolExecutor`` instead. This is the same category of infrastructure swap
as Redis->Local exchange: the real Parsl ``@python_app`` and the agent logic are
untouched -- only WHERE the task runs changes. The Aurora copy is identical: these
exercises run on a single CPU node, so both use ``ThreadPoolExecutor``.
"""
from __future__ import annotations

import asyncio

import parsl
from parsl import Config
from parsl.executors.threads import ThreadPoolExecutor  # local swap for HTEX

from academy.agent import action
from academy.agent import Agent


@parsl.python_app
def expensive_task() -> int:
    # Do expensive task
    return 42


class SimulationAgent(Agent):
    def __init__(self) -> None:
        self.config = Config(
            executors=[
                ThreadPoolExecutor(label="local_threads", max_threads=2),
            ],
        )

    async def agent_on_startup(self) -> None:
        self.dfk = parsl.load(self.config)

    async def agent_on_shutdown(self) -> None:
        self.dfk.cleanup()
        self.dfk = None
        parsl.clear()

    @action
    async def run_expensive_task(self) -> int:
        return await asyncio.wrap_future(expensive_task())
