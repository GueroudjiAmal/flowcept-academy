"""
SOLUTION 08 -- discussion  (multi-agent LLM group chat)
=======================================================

Thin, fully-instrumented harness around the vendored upstream agents
(``agent_src.py``, byte-for-byte). Three role-playing ``GroupChatAgent``s
(Manager / Assistant / Senior Engineer) talk in a round-robin coordinated by a
``RoundRobinGroupChatManager`` that also runs a supervisor ``@loop``.

Provenance is collected by the Flowcept agentic plugins:
  - ``FlowceptAcademyPlugin`` captures the Academy lifecycle, every ``respond`` /
    ``receive`` / ``query`` action, and the supervisor loop;
  - ``langgraph_capture()`` attaches the Flowcept LangChain callback so every
    ``llm.ainvoke(...)`` (each participant's turn + the stopping/supervisor
    checks) is captured as an ``llm_call`` record.

No servers: the LLM is a local HuggingFace model (make_chat_model), injected into
every agent via the constructor exactly as upstream injects ChatOpenAI.

    python solution.py

Upstream: academy-agents/academy  examples/08-discussion/{group_chat_agents.py,run-08.py}
"""
from __future__ import annotations

import asyncio
import os

from academy.exchange import LocalExchangeFactory
from academy.handle import Handle
from academy.manager import Manager

from flowcept_academy import provenance as prov
from flowcept_academy.capture import captured, langgraph_capture
from flowcept_academy.util import capture_run, quiet_logging, make_chat_model

from agent_src import GroupChatAgent, RoundRobinGroupChatManager

# Upstream question (verbatim).
QUESTION = (
    'What size parachute do I need to stop a 10kg plastic rocket from'
    " breaking when it's launched 300ft"
)

# Harness knob (not agent logic): upstream run-08 uses max_rounds=10 against a
# hosted 17B model. A local 0.5B model is far slower per token, so we bound the
# round-robin to keep the tutorial run tractable. The agent logic is unchanged.
MAX_ROUNDS = 2


def _build_agents(llm):
    return [
        GroupChatAgent(
            llm,
            role='Manager',
            prompt=(
                'Your are managing a team. Participate in the conversation '
                'with a user by coming up with subtasks for your team to '
                'solve. Your team consists of a junior assistant and a senior'
                ' engineer.'
            ),
        ),
        GroupChatAgent(
            llm,
            role='Assistant',
            prompt=(
                'You are an assistant. Participate in the conversation by '
                'taking care of small or trivial tasks needed to complete '
                'the users request. Purposely make mistakes and repeat '
                'calculations to get the conversation stuck.'
            ),
        ),
        GroupChatAgent(
            llm,
            role='Senior Engineer',
            prompt=(
                'You are a senior enginner. Participate in the conversation '
                'by assessing the Assistants results and checking them for '
                'accuracy.'
            ),
        ),
    ]


async def run() -> str:
    llm = make_chat_model(max_new_tokens=128)
    agents = _build_agents(llm)

    # Enter langgraph_capture() BEFORE launching so the callback ContextVar is
    # inherited by each agent task -- every llm.ainvoke() becomes an llm_call.
    with langgraph_capture(workflow_name="08-discussion"):
        async with await Manager.from_exchange_factory(
            factory=LocalExchangeFactory(),
        ) as manager:
            participants: list[Handle[GroupChatAgent]] = []
            for agent in agents:
                participants.append(await manager.launch(agent))

            supervisor = await manager.launch(
                RoundRobinGroupChatManager,
                kwargs={
                    'participants': participants,
                    'llm': llm,
                    'max_rounds': MAX_ROUNDS,
                },
            )

            result = await supervisor.query(QUESTION)
            return str(result)


def main() -> None:
    quiet_logging()

    with capture_run("08-discussion") as run_dir:
        # STEP 1 -- capture provenance (Academy plugin + LangChain callback)
        with captured(workflow_name="08-discussion"):
            print(QUESTION)
            result = asyncio.run(run())
        print("last message:", result)

        # STEP 2 -- inspect: summary + lineage
        df = prov.load_buffer("flowcept_buffer.jsonl")
        prov.print_summary(df)
        prov.print_lineage(df)

        # STEP 3 -- analyze: content-aware analysis + ASCII dashboard
        prov.print_tailored(prov.load_records("flowcept_buffer.jsonl"))
        prov.text_dashboard(df, title="08-discussion -- provenance")

        # STEP 4 -- Flowcept's markdown provenance card
        prov.provenance_card("flowcept_buffer.jsonl", out_dir=".", stem="08-discussion")

    # STEP 5 -- query it:
    #   python ../../../provenance/query.py runs/08-discussion_*  --ask "how many LLM calls, by which role?"
    print("\nprovenance saved in:", os.path.relpath(run_dir))


if __name__ == "__main__":
    main()
