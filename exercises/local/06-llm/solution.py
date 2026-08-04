"""
SOLUTION 06 -- llm  (LLM-driven ReACT loop calling a tool agent)
================================================================

Thin, fully-instrumented harness around the vendored upstream agents
(``agent_src.py``). The Orchestrator builds a LangChain ReACT agent (``create_agent``)
over a tool that messages ``MySimAgent`` -- the LLM decides when to call the tool.

Provenance is collected by the Flowcept agentic plugins:
  - ``FlowceptAcademyPlugin`` captures the Academy lifecycle + ``answer`` /
    ``compute_ionization_energy`` actions (cross-agent tool call);
  - ``langgraph_capture()`` attaches the Flowcept LangGraph callback so the
    ReACT loop's LLM calls / tool calls are captured too.

LLM backend routes via ``make_chat_model()``: Argo (``ARGO_USER``) → vLLM
(``VLLM_BASE_URL``) → OpenAI (``OPENAI_API_KEY``) → local HuggingFace CPU model, in priority order. No servers
or keys are required for the local path (see agent_src.make_chat_model).

    python solution.py

Upstream: academy-agents/academy  examples/06-llm/run-06.py
"""
from __future__ import annotations

import asyncio
import os

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured, langgraph_capture
from flowcept_academy.util import capture_run, quiet_logging

from agent_src import MySimAgent, Orchestrator

QUESTION = 'What is the simulated ionization energy of benzene?'


async def run() -> str:
    # Enter langgraph_capture() BEFORE launching agents: it sets a ContextVar that
    # LangChain copies into each agent task's context at launch time. Attaching it
    # here means the ReACT loop's llm_call / tool_call records are captured with no
    # edit to the agent code.
    with langgraph_capture(workflow_name="06-llm"):
        async with await Manager.from_exchange_factory(
            factory=LocalExchangeFactory(),
        ) as manager:
            simulator = await manager.launch(MySimAgent)
            orchestrator = await manager.launch(
                Orchestrator,
                kwargs={
                    # model/access_token/base_url are upstream constructor args; the
                    # routed backend ignores them (see agent_src.make_chat_model).
                    'model': 'local',
                    'access_token': 'none',
                    'simulators': [simulator],
                    'base_url': None,
                },
            )
            result = await orchestrator.answer(QUESTION)
            return str(result)


def main() -> None:
    quiet_logging()

    with capture_run("06-llm") as run_dir:
        # STEP 1 -- capture provenance (Academy plugin + LangGraph callback)
        with captured(workflow_name="06-llm"):
            print(QUESTION)
            result = asyncio.run(run())
        print("result:", result)

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="06-llm -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="06-llm")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/06-llm_*  --ask "which tool did the LLM call?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
