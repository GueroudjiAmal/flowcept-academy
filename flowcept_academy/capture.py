"""A single, deterministic way to turn provenance capture on and off.

Why this exists
---------------
There are two ways to run the Flowcept Academy plugin:

1. **Explicit** -- ``FlowceptAcademyPlugin(config={...}).start()`` / ``.stop()``.
2. **Zero-code** -- enable it in ``settings.yaml`` and a bare ``with Flowcept():``
   auto-starts it.

If *both* happen (e.g. your global ``~/.flowcept/settings.yaml`` enables the
plugin *and* you also start one by hand) you get two plugin instances, two
overhead reports, and two perf CSVs -- confusing in a classroom. ``captured()``
gives one deterministic behavior regardless of the attendee's settings:

* start Flowcept (which auto-starts the plugin *iff* settings enable it),
* if no Academy interceptor is active yet, start exactly one,
* on exit, stop only what we started, then stop Flowcept.

So every module gets exactly one capture, one report, one perf CSV.

Usage::

    from flowcept_academy.capture import captured
    with captured(workflow_name="module3") as fc:
        run(my_academy_app())        # everything here is captured
    # provenance is now flushed to flowcept_buffer.jsonl
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Iterator

# The FlowceptAcademyPlugin instance started by the most recent captured() block
# (None if the plugin was auto-started from settings.yaml instead). Exposed so a
# cross-framework example (e.g. 07 = Academy + LangGraph) can compose a LangGraph
# plugin via FlowceptLangGraphPlugin.from_academy_plugin(active_academy_plugin()).
_ACTIVE_PLUGIN: Any = None


def active_academy_plugin() -> Any:
    """Return the FlowceptAcademyPlugin started by the current captured() block."""
    return _ACTIVE_PLUGIN


# ---------------------------------------------------------------------------
# Cross-framework (Academy + LangGraph) capture with ZERO agent-code changes
# ---------------------------------------------------------------------------
# Example 07 runs a LangGraph reasoning graph *inside* an Academy @loop. To capture
# langgraph_graph/langgraph_node records we must attach Flowcept's LangChain
# callback handler to every graph/LLM/tool run -- but we may not edit the vendored
# agent to thread `config={"callbacks":[...]}` into its `.ainvoke(...)` calls.
#
# LangChain's `register_configure_hook(context_var, inheritable=True)` solves this:
# when the ContextVar holds a handler *instance*, LangChain's callback manager adds
# it (inheritably) to EVERY run in the current context -- so it flows into nested
# graph nodes and LLM calls with no code change. It propagates across asyncio tasks
# and copied contexts (hence 07 runs its @loop in-process), but not across separate
# processes.
_LANGGRAPH_CB_VAR: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "flowcept_langgraph_cb", default=None
)
_HOOK_REGISTERED = False


def _ensure_hook_registered() -> None:
    global _HOOK_REGISTERED
    if _HOOK_REGISTERED:
        return
    from langchain_core.tracers.context import register_configure_hook

    # handle_class=None -> LangChain uses whatever instance the ContextVar holds.
    register_configure_hook(_LANGGRAPH_CB_VAR, True)
    _HOOK_REGISTERED = True


@contextlib.contextmanager
def langgraph_capture(workflow_name: str = "langgraph") -> Iterator[Any]:
    """Attach Flowcept's LangGraph callback globally for the duration of the block.

    Must be used *inside* a :func:`captured` block (so an Academy plugin is active
    to share its ``campaign_id``). Yields the ``FlowceptLangGraphPlugin`` (or
    ``None`` if unavailable). Zero edits to the vendored agent are required.

    Usage::

        with captured(workflow_name="07-mol-design"):
            with langgraph_capture("07-mol-design"):
                run(my_academy_app())   # LangGraph nodes/graphs captured too
    """
    plugin = None
    token = None
    try:
        from flowcept.agents.langgraph.langgraph_plugin import FlowceptLangGraphPlugin

        _ensure_hook_registered()
        plugin = FlowceptLangGraphPlugin.from_academy_plugin(
            active_academy_plugin(), {"workflow_name": workflow_name}
        )
        token = _LANGGRAPH_CB_VAR.set(plugin.callback_handler)
    except Exception:
        plugin = None
    try:
        yield plugin
    finally:
        if token is not None:
            _LANGGRAPH_CB_VAR.reset(token)
        # from_academy_plugin() gives the LangGraph plugin its OWN interceptor
        # (_owns_interceptor=True). Its node/llm_call/tool_call task records are
        # buffered and only flushed on stop(); the immediate workflow messages
        # aren't enough. Stop it here (before captured()'s own stop) so every
        # LangGraph task lands in the same flowcept_buffer.jsonl.
        if plugin is not None:
            try:
                plugin.stop()
            except Exception:
                pass


@contextlib.contextmanager
def captured(
    workflow_name: str = "academy-tutorial",
    performance_tracking: bool = True,
) -> Iterator[object]:
    """Context manager that captures Academy provenance exactly once."""
    global _ACTIVE_PLUGIN
    from flowcept import Flowcept
    import flowcept.agents.academy.academy_plugin as ap
    from flowcept.agents.academy.academy_plugin import FlowceptAcademyPlugin

    fc = Flowcept(workflow_name=workflow_name)
    fc.start()

    started_here = None
    if ap._ACTIVE_INTERCEPTOR is None:  # settings did not auto-start one
        started_here = FlowceptAcademyPlugin(
            config={
                "enabled": True,
                "workflow_name": workflow_name,
                "performance_tracking": performance_tracking,
                # Share Flowcept's campaign so every record lands under one
                # campaign_id -> a single, coherent provenance graph.
                "campaign_id": fc.campaign_id,
            }
        ).start()
    _ACTIVE_PLUGIN = started_here

    try:
        yield fc
    finally:
        if started_here is not None:
            started_here.stop()
        _ACTIVE_PLUGIN = None
        fc.stop()
