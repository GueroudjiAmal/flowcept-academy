"""Vendored VERBATIM from the upstream Academy example (agent logic only).

Source: academy-agents/academy  examples/01-actor-client/run-01.py

Only the agent class is vendored here, unchanged -- the run harness (Manager,
exchange, executor, bounds) lives in solution.py / exercise.py so Flowcept
provenance is wired *around* this code without editing it.
"""
from __future__ import annotations

from academy.agent import Agent
from academy.agent import action


class Counter(Agent):
    count: int

    async def agent_on_startup(self) -> None:
        self.count = 0

    @action
    async def increment(self, value: int = 1) -> None:
        self.count += value

    @action
    async def get_count(self) -> int:
        return self.count
