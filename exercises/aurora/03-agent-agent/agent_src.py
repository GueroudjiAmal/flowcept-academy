"""Vendored VERBATIM from the upstream Academy example (agent logic only).

Source: academy-agents/academy  examples/03-agent-agent/run-03.py
        https://github.com/academy-agents/academy/blob/main/examples/03-agent-agent/run-03.py

Only the agent classes are vendored here, unchanged -- the run harness lives in
solution.py / exercise.py so the Flowcept plugins wrap this code without editing it.
"""
from __future__ import annotations

from academy.agent import action
from academy.agent import Agent
from academy.handle import Handle


class Coordinator(Agent):
    def __init__(
        self,
        lowerer: Handle[Lowerer],
        reverser: Handle[Reverser],
    ) -> None:
        super().__init__()
        self.lowerer = lowerer
        self.reverser = reverser

    @action
    async def process(self, text: str) -> str:
        text = await self.lowerer.lower(text)
        text = await self.reverser.reverse(text)
        return text


class Lowerer(Agent):
    @action
    async def lower(self, text: str) -> str:
        return text.lower()


class Reverser(Agent):
    @action
    async def reverse(self, text: str) -> str:
        return text[::-1]
