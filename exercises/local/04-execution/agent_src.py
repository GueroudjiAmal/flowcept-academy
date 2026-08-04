"""Agent for example 04 -- an agent that offloads CPU work to SEPARATE PROCESSES.

Why this differs from the other examples' ``agent_src.py``
---------------------------------------------------------
Upstream Academy example 04 ("04-execution") runs the *same three agents as
example 03* inside a ``ProcessPoolExecutor`` over an HTTP exchange -- i.e. the
agents themselves run in separate OS processes. Flowcept can capture provenance
from those worker processes, but it aggregates the per-worker records through its
**message queue** (online mode). This tutorial runs fully **offline** (no Redis
MQ, no MongoDB -- records are dumped to ``flowcept_buffer.jsonl``), and offline
there is no MQ for the workers to flush through, so worker-process records are
lost. Reproducing the upstream harness verbatim here would therefore capture an
empty (task-less) buffer.

So example 04 demonstrates the SAME capability -- Flowcept's
``make_process_executor`` (real multi-process execution) -- in the shape that
captures reliably offline: a single agent runs **in this process** (so the
Academy plugin captures its lifecycle and its ``@action``), and the ``@action``
offloads the heavy work to a pool of **separate worker processes** built with
``make_process_executor``. Each result records the ``pid``/``host`` it ran on, so
the ``compute`` action's ``generated`` payload proves the work really crossed the
process boundary -- and that lineage lives in the offline buffer.

The pool is injected via ``set_executor()`` (called by the harness after the
plugin is active) rather than passed through ``manager.launch`` so the agent
stays free of harness plumbing.
"""
from __future__ import annotations

import asyncio
import os
import socket
from concurrent.futures import ProcessPoolExecutor

from academy.agent import Agent
from academy.agent import action

# The process pool the agent offloads to. Set by the harness (set_executor)
# after the Academy plugin is active, so make_process_executor can wire each
# worker for provenance capture. Kept module-level so it need not be pickled
# through manager.launch (the agent runs in-process under LocalExchangeFactory).
_EXECUTOR: ProcessPoolExecutor | None = None


def set_executor(executor: ProcessPoolExecutor) -> None:
    """Give the agent the process pool to offload work to."""
    global _EXECUTOR
    _EXECUTOR = executor


def _work(n: int) -> dict:
    """CPU work run in a SEPARATE worker process.

    Returns the answer together with the ``pid``/``host`` it ran on, so the
    captured provenance records *where* each unit of work executed.
    """
    total = sum(i * i for i in range(n * 50_000))
    return {"n": n, "sum_sq": total, "pid": os.getpid(), "host": socket.gethostname()}


class Distributor(Agent):
    """An agent that fans a batch of tasks out to separate worker processes."""

    @action
    async def compute(self, sizes: list[int]) -> list[dict]:
        """Offload each size to a worker PROCESS and gather the results.

        The action itself runs in this process (captured as an
        ``academy_action``); the ``_work`` calls run in the pool's separate
        processes -- each returned dict names the pid/host it ran on.
        """
        loop = asyncio.get_running_loop()
        futures = [loop.run_in_executor(_EXECUTOR, _work, s) for s in sizes]
        return list(await asyncio.gather(*futures))
