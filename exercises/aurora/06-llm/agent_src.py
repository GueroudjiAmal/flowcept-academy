"""Vendored VERBATIM from the upstream Academy example (agent logic only).

Source: academy-agents/academy  examples/06-llm/run-06.py
        https://github.com/academy-agents/academy/blob/main/examples/06-llm/run-06.py

Only the agent classes are vendored here -- the run harness lives in
solution.py / exercise.py so the Flowcept plugins wrap this code without editing it.

The ONE sanctioned change vs upstream: the LLM construction site. Upstream builds
``ChatOpenAI(model=..., api_key=..., base_url=...)`` (an OpenAI-compatible server);
here we build the model via ``make_chat_model()``, which routes (in priority order)
to Argo when ``ARGO_USER`` is set, else vLLM when ``VLLM_BASE_URL`` is set, else
OpenAI when ``OPENAI_API_KEY`` is set, else a **local** HuggingFace CPU model -- the
same agent code every way (no servers or keys required for the local path). A
tool-capable backend (Argo/vLLM/OpenAI) exercises
the full ReACT tool call; the local 0.5B model answers directly without a tool
call. The agent logic -- ``MySimAgent``, ``make_sim_tool``, the ReACT loop via
``create_agent`` -- is byte-for-byte upstream.
"""
from __future__ import annotations

import logging

from langchain.agents import create_agent
# UPSTREAM: `from langchain.tools import Tool` -- in langchain 1.3 the `Tool`
# *type* moved to langchain_core.tools (the `tool` decorator stayed put). This is
# a version-compat import shim only; no agent logic changes.
from langchain_core.tools import Tool
from langchain.tools import tool

from academy.agent import action
from academy.agent import Agent
from academy.handle import Handle

from flowcept_academy.util import make_chat_model

logger = logging.getLogger(__name__)


# An Academy agent that wraps computational tools: in this case,
# a single function that runs locally.
#
# A more sophisticated version might:
#  -- Wrap multiple tools
#  -- Dispatch tool calls to an HPC system
#
# Note that the agent and individual tools have doc strings,
# these are used by the LLM when generating tool calls.
class MySimAgent(Agent):
    """Agent for running tools to characterize molecules."""

    @action
    async def compute_ionization_energy(self, smiles: str) -> float:
        """Compute the ionization energy for the given molecule."""
        return 0.5


def make_sim_tool(handle: Handle[MySimAgent]) -> Tool:
    """Wraps an academy handle in a langchain tool.

    Note: Since the documentation of the tool is used by the language
    model, a specific wrapper method may need to be written per agent.
    """

    @tool
    async def compute_ionization_energy(smiles: str) -> float:
        """Compute the ionization energy of a molecule."""
        return await handle.compute_ionization_energy(smiles)

    return compute_ionization_energy


# An Academy agent that creates a LangChain agent that will respond to
# questions about molecules by running a ReACT loop
class Orchestrator(Agent):
    """Orchestrate a scientific workflow."""

    def __init__(
        self,
        model: str,
        access_token: str,
        simulators: list[Handle[MySimAgent]],
        base_url: str | None = None,
    ):
        self.model = model
        self.access_token = access_token
        self.base_url = base_url
        self.simulators = simulators

    async def agent_on_startup(self) -> None:
        # UPSTREAM: llm = ChatOpenAI(model=..., api_key=..., base_url=...)
        # Local swap: a HuggingFace chat model (no server / no key).
        llm = make_chat_model()

        tools = [make_sim_tool(agent) for agent in self.simulators]
        # The following call creates the LangChain agent
        self.react_loop = create_agent(llm, tools=tools)

    @action
    async def answer(self, goal: str) -> str:
        """Use other agents to answer questions about molecules."""

        # This call runs the ReACT loop, in which:
        #   1) the LLM is used to determine which tool to call,
        #   2) the tool is called (by messaging the Academy agent)
        return await self.react_loop.ainvoke(
            {'messages': [{'role': 'user', 'content': goal}]},
        )
