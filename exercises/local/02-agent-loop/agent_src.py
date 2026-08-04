"""Vendored VERBATIM from the upstream Academy example (agent logic only).

Source: academy-agents/academy  examples/02-agent-loop/run-02.py

Only the agent class is vendored here, unchanged -- the run harness lives in
solution.py / exercise.py so Flowcept provenance is wired around this code.
"""
from __future__ import annotations

import asyncio

from academy.agent import Agent
from academy.agent import action
from academy.agent import loop


class Counter(Agent):
    count: int

    async def agent_on_startup(self) -> None:
        self.count = 0

    @loop
    async def increment(self, shutdown: asyncio.Event) -> None:
        while not shutdown.is_set():
            await asyncio.sleep(1)
            self.count += 1

    @action
    async def get_count(self) -> int:
        return self.count
