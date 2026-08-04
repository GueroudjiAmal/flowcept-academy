"""
SOLUTION 07 -- mol-design  (real GFN2-xTB molecular-design campaign)
====================================================================

Thin, fully-instrumented harness around the vendored upstream agent
(``agent_src.py`` = ``mol_design_agents.py``, byte-for-byte apart from the LLM
construction site). This is the REAL-chemistry example: an ``XTBSimulationAgent``
runs an LLM reasoning campaign, built as a LangGraph ``StateGraph`` inside an
Academy ``@loop``, that proposes molecules and evaluates their ionization energy
with **actual GFN2-xTB** relaxations (rdkit + ASE + xtb). Nothing is mocked.

Provenance is collected by the Flowcept agentic plugins:
  - ``FlowceptAcademyPlugin`` captures the Academy lifecycle, the
    ``conduct_simulation_campaign`` ``@loop``, the ``compute_ionization_energy``
    action, and the ``report`` action;
  - ``langgraph_capture()`` attaches the Flowcept LangChain callback so the
    reasoning graph (``langgraph_graph``), each node (``langgraph_node``), each
    ``llm.ainvoke`` (``llm_call``) and each tool call (``tool_call``) are captured
    -- with zero edits to the vendored agent.

LLM: ``make_chat_model()`` routes (in priority order) to Argo (real OpenAI-compatible
endpoint, native tool calling) when ``ARGO_USER`` is set, else vLLM when
``VLLM_BASE_URL`` is set, else OpenAI when ``OPENAI_API_KEY`` is set, else a local
HuggingFace model -- the SAME agent code every way. 07's ``tool_calling`` node has an unbounded retry that waits for a parseable tool
call, so run this with a tool-capable backend (``ARGO_USER=... python solution.py`` or
``OPENAI_API_KEY=... python solution.py``). The default local 0.5B model does not emit
tool calls and will not terminate that node.

Harness changes vs upstream run-07.py (outer harness only; agent logic unchanged):
  - RedisExchangeFactory -> LocalExchangeFactory (no Redis server);
  - HighThroughputExecutor + ParslPoolExecutor -> in-process (agents run as asyncio
    tasks in this process, so the LangChain callback ContextVar propagates; the xTB
    work still runs in the agent's own ProcessPoolExecutor, i.e. real parallelism);
  - ``while True: sleep 30`` -> a bounded poll loop; exiting the Manager context
    shuts the agents down, which sets each ``@loop``'s shutdown event so
    ``should_continue`` returns END and the campaign graph terminates cleanly.

Requires the flowcept-academy conda env (setup/environment.yml):
    conda activate flowcept-academy && python solution.py

Upstream: academy-agents/academy  examples/07-mol-design/{mol_design_agents.py,run-07.py}
"""
from __future__ import annotations

import asyncio
import logging
import os

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured, langgraph_capture
from flowcept_academy.util import capture_run, quiet_logging

from agent_src import XTBConfig, XTBSimulationAgent

# Upstream seeds are ['CNC(N)=O', 'CC1=C(O)N=C(O)N1']. A campaign per seed runs a
# full LLM+xTB reasoning loop; for a tractable tutorial run we seed ONE campaign.
# This is a harness knob (how many campaigns to launch), not an agent-logic change.
SEEDS = ['CNC(N)=O']

# Harness knob (not agent logic): upstream polls forever (`while True: sleep 30`).
# We poll a bounded number of times, then exit the Manager context -- which shuts
# the agents down and terminates each campaign graph via its shutdown event.
#
# Why several polls (not 1-2): each campaign round can propose SMILES the model
# writes in chemistry shorthand (e.g. `CNC(NO2)=O`), which RDKit rejects. The
# upstream graph is *designed* to recover -- the conclude/critique/update nodes
# feed the parse failures back to the LLM, which fixes the SMILES next round. We
# give it that room, and stop early (see run()) the moment real energies appear.
MAX_POLLS = 6
POLL_SECONDS = 45


async def run() -> list:
    # Enter langgraph_capture() BEFORE launching agents so the callback ContextVar
    # is inherited by each agent's asyncio task -- the reasoning graph, its nodes,
    # every llm.ainvoke() and tool call are captured with no edit to the agent.
    with langgraph_capture(workflow_name="07-mol-design"):
        async with await Manager.from_exchange_factory(
            factory=LocalExchangeFactory(),
        ) as manager:
            agents = []
            for molecule in SEEDS:
                agents.append(
                    await manager.launch(
                        XTBSimulationAgent,
                        args=(XTBConfig(), molecule),
                    ),
                )

            print('Starting discovery campaign')
            print('=' * 80)
            reports: list = []
            for _ in range(MAX_POLLS):
                await asyncio.sleep(POLL_SECONDS)
                per_agent: list = []
                for i, agent in enumerate(agents):
                    report = await agent.report()
                    per_agent.append(report)
                    reports = report
                    print(f'Progress report from agent {i}')
                    print(f'Number of molecules simulated: {len(report)}')
                    print(f'Five best molecules: {report[:5]}')
                print('=' * 80)
                # Stop early once the campaign has produced real xTB energies --
                # no need to keep polling once every seed has simulated molecules.
                if all(len(r) > 0 for r in per_agent):
                    break
            # Leaving the context shuts agents down -> each @loop's shutdown event
            # is set -> should_continue returns END -> the campaign graph finishes.
            return reports


def main() -> None:
    quiet_logging()
    # Presentation only (not agent logic): when the LLM proposes an invalid SMILES,
    # the vendored campaign's fire-and-forget tool tasks surface asyncio's
    # "Task exception was never retrieved" ERROR with a full traceback. The parse
    # failure is already shown as a one-line RDKit "SMILES Parse Error", so silence
    # asyncio's redundant traceback to keep the tutorial output readable.
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    with capture_run("07-mol-design") as run_dir:
        # STEP 1 -- capture provenance (Academy plugin + LangGraph callback)
        with captured(workflow_name="07-mol-design"):
            print("seeds:", SEEDS)
            best = asyncio.run(run())
        print("best molecules:", best[:5])

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="07-mol-design -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="07-mol-design")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/07-mol-design_*  --ask "which molecules were simulated and what were their ionization energies?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
