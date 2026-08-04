"""
EXERCISE 07 -- mol-design  (real GFN2-xTB molecular-design campaign)
====================================================================

WHAT THIS IS
    The stock Academy example (agent code vendored unchanged in agent_src.py):
    an `XTBSimulationAgent` runs an LLM reasoning campaign -- a LangGraph
    `StateGraph` inside an Academy `@loop` -- that proposes molecules and scores
    them by **real GFN2-xTB ionization energy** (rdkit + ASE + xtb, nothing
    mocked). As shipped it RUNS but records NO provenance. Uncomment one STEP
    block at a time in main() and re-run.

HOW TO RUN (needs the flowcept-academy conda env AND a tool-capable LLM backend)
    conda activate flowcept-academy && ARGO_USER=<you> python exercise.py

WHAT THE PROVENANCE REVEALS
    A single provenance graph spanning THREE layers, all sharing one campaign_id:
      - Academy plugin: agent lifecycle, the `conduct_simulation_campaign` @loop,
        each `compute_ionization_energy` action (the real xTB calls), `report`.
      - LangChain callback (langgraph_capture): the reasoning graph
        (`langgraph_graph`), every node (plan / tool_calling / simulate / conclude
        / critique / update), each `llm.ainvoke` (`llm_call`) and each tool call
        (`tool_call`) -- with zero edits to the agent.
      - The molecule -> ionization-energy results are REAL xTB numbers.

NOTE (backend): `make_chat_model()` routes (in priority order) to Argo (native tool
calling) when ARGO_USER is set, else OpenAI when OPENAI_API_KEY is set, else a local
HuggingFace model. 07's `tool_calling` node retries until it gets a parseable tool
call, so it needs a tool-capable backend -- run with ARGO_USER or OPENAI_API_KEY set.
The agent logic is byte-for-byte upstream (only the LLM constructor is routed).

Reference: solution.py.  Upstream: academy-agents/academy examples/07-mol-design/
"""
from __future__ import annotations

import asyncio

from academy.exchange import LocalExchangeFactory
from academy.manager import Manager

from agent_src import XTBConfig, XTBSimulationAgent  # <- vendored upstream

SEEDS = ['CNC(N)=O']   # harness knob: how many campaigns to seed (upstream: 2)
MAX_POLLS = 2          # harness knob: upstream polls forever (`while True`)
POLL_SECONDS = 45


async def run() -> list:
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
            for i, agent in enumerate(agents):
                report = await agent.report()
                reports = report
                print(f'Progress report from agent {i}')
                print(f'Number of molecules simulated: {len(report)}')
                print(f'Five best molecules: {report[:5]}')
            print('=' * 80)
        return reports


def main() -> None:
    import os
    from flowcept_academy.util import quiet_logging
    quiet_logging()

    # =====================================================================
    # STEP 0 -- BASELINE. Run the campaign; print the best molecules. No provenance.
    # =====================================================================
    print("seeds:", SEEDS)
    best = asyncio.run(run())
    print("best molecules:", best[:5])

    # =====================================================================
    # STEPS 1-4 -- turn provenance on. Uncomment; reveal inner STEPs one at a time.
    # For the LangGraph node/llm_call/tool_call records, wrap run() in
    # langgraph_capture() (see solution.py) and enter it BEFORE launching the agents.
    # =====================================================================
    # from flowcept_academy import provenance as prov
    # from flowcept_academy.capture import captured
    # from flowcept_academy.util import capture_run
    #
    # with capture_run("07-mol-design") as run_dir:
    #     # STEP 1 -- CAPTURE (Academy plugin + LangChain callback)
    #     with captured(workflow_name="07-mol-design"):
    #         best = asyncio.run(run())     # run() must enter langgraph_capture() -- see solution.py
    #     print("best molecules:", best[:5])
    #
    #     # STEP 2 -- INSPECT
    #     df = prov.load_buffer("flowcept_buffer.jsonl")
    #     prov.print_summary(df)
    #     prov.print_lineage(df)
    #
    #     # STEP 3 -- ANALYZE
    #     prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
    #     prov.text_dashboard(df, title="07-mol-design -- provenance")
    #
    #     # STEP 4 -- CARD
    #     prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="07-mol-design")
    # print("\nprovenance saved in:", os.path.relpath(run_dir))
    #
    # =====================================================================
    # STEP 5 -- QUERY:
    #   python ../../../provenance/query.py runs/07-mol-design_*  --ask "which molecules were simulated and what were their ionization energies?"
    # =====================================================================


if __name__ == "__main__":
    main()
