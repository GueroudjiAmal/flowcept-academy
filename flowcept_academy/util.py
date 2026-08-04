"""Small utilities shared by the tutorial scripts and notebooks."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any, Coroutine, Iterator


def new_run_dir(name: str, base: str = "runs") -> str:
    """Create and return a fresh per-run output directory.

    Each run's provenance (buffer, perf CSV, dashboard) goes into its own
    ``runs/<name>_<YYYYmmdd-HHMMSS>/`` directory so repeated runs never overwrite
    each other. A numeric suffix is added if two runs start in the same second.
    """
    ts = time.strftime("%Y%m%d-%H%M%S")
    cand = os.path.join(base, f"{name}_{ts}")
    n = 0
    while os.path.exists(cand):
        n += 1
        cand = os.path.join(base, f"{name}_{ts}_{n}")
    os.makedirs(cand)
    return os.path.abspath(cand)


@contextlib.contextmanager
def capture_run(name: str, base: str = "runs") -> Iterator[str]:
    """Run inside a fresh ``runs/<name>_<date-time>/`` directory.

    Creates the per-run dir under the current directory and ``chdir``s into it so
    *every* artifact a run produces -- ``flowcept_buffer.jsonl``, the perf CSV(s),
    and the markdown provenance card -- lands together in that one folder. Restores
    the original working directory on exit and yields the run dir's absolute path.

    Usage::

        with capture_run("06-llm") as rd:      # -> ./runs/06-llm_<date-time>/
            with captured(workflow_name="06-llm"):
                result = asyncio.run(run())
            # inspect / analyze / card here -- all files land in rd
        print("provenance saved in", os.path.relpath(rd))
    """
    prev = os.getcwd()
    d = new_run_dir(name, base)
    os.chdir(d)
    try:
        yield d
    finally:
        os.chdir(prev)


def run(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run *coro* to completion from a script **or** a Jupyter cell.

    Academy is asyncio-based, so every example ends up calling an ``async def``.
    In a plain script ``asyncio.run`` just works. Inside Jupyter there is already
    a running event loop, so ``asyncio.run`` would raise; we apply ``nest_asyncio``
    (if available) to allow re-entrancy. This keeps a single code path working in
    both the ``scripts/`` and ``notebooks/`` versions of every module.
    """
    try:
        import nest_asyncio

        nest_asyncio.apply()
    except Exception:
        pass
    return asyncio.run(coro)


def quiet_logging() -> None:
    """Silence Academy/Flowcept INFO chatter so tutorial output stays readable."""
    logging.disable(logging.WARNING)


# Cache the loaded model+tokenizer so repeated make_chat_model() calls (e.g. an
# example that builds a reasoning and a generation model) don't reload weights.
_CHAT_MODEL_CACHE: dict[tuple[str, int], Any] = {}

# Small, instruction-tuned model that runs on CPU and is already cached locally.
DEFAULT_CHAT_MODEL = os.environ.get(
    "FLOWCEPT_TUTORIAL_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"
)

# Argo (ANL's OpenAI-compatible LLM gateway). Selected when ARGO_USER is set.
ARGO_BASE_URL = os.environ.get(
    "ARGO_BASE_URL", "https://apps.inside.anl.gov/argoapi/v1"
)
ARGO_MODEL = os.environ.get("ARGO_MODEL", "gpt4o")

# OpenAI (the real api.openai.com). Selected when OPENAI_API_KEY is set and Argo
# is not. Any tool-capable chat model works; gpt-4o-mini is a cheap default.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def which_backend() -> str:
    """Which LLM backend make_chat_model() will use.

    Returns ``"argo"``, ``"openai"``, or ``"local"``. Routing is by environment so
    the *agent code is identical* whichever backend is chosen:

      * ``FLOWCEPT_TUTORIAL_LLM`` (``"argo"``/``"openai"``/``"local"``) forces the
        backend -- e.g. Aurora compute nodes set ``local`` to stay fully offline;
      * else ``ARGO_USER`` set -> **Argo** (ANL's OpenAI-compatible gateway, native
        tool calling);
      * else ``OPENAI_API_KEY`` set -> **OpenAI** (api.openai.com, native tool
        calling);
      * otherwise -> a small **local** HuggingFace model (no servers/keys, CPU).

    Argo and OpenAI both support tool calls, which the examples that need them
    (e.g. 07's tool_calling node) depend on; the local 0.5B model does not.
    """
    forced = os.environ.get("FLOWCEPT_TUTORIAL_LLM", "").strip().lower()
    if forced in ("local", "argo", "openai"):
        return forced
    if os.environ.get("ARGO_USER"):
        return "argo"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "local"


def make_chat_model(
    model_id: str | None = None,
    *,
    max_new_tokens: int = 512,
    temperature: float = 0.0,
):
    """Return a LangChain chat model -- Argo, OpenAI, *or* a local HuggingFace model.

    This is the single LLM construction site for the examples (06/07/08) that
    upstream build with ``ChatOpenAI(...)``. The **same agent code** works with
    any backend; :func:`which_backend` picks one from the environment:

      * ``ARGO_USER`` set -> a real ``ChatOpenAI`` pointed at Argo's
        OpenAI-compatible endpoint (``ARGO_BASE_URL``, model ``ARGO_MODEL``).
        Supports ``.bind_tools`` with native tool calling.
      * else ``OPENAI_API_KEY`` set -> a real ``ChatOpenAI`` on api.openai.com
        (model ``OPENAI_MODEL``). Native tool calling.
      * otherwise -> a local ``ChatHuggingFace`` over ``DEFAULT_CHAT_MODEL``
        (``FLOWCEPT_TUTORIAL_MODEL``), CPU, no servers/keys.

    All return a LangChain chat model with ``.invoke``/``.ainvoke``/``.bind_tools``,
    so the vendored agent code runs unchanged. Instances are cached across calls.
    """
    backend = which_backend()
    if backend == "argo":
        from langchain_openai import ChatOpenAI

        argo_user = os.environ["ARGO_USER"]
        model = os.environ.get("ARGO_MODEL", ARGO_MODEL)
        key = ("argo", ARGO_BASE_URL, model, argo_user, temperature)
        chat = _CHAT_MODEL_CACHE.get(key)
        if chat is None:
            chat = ChatOpenAI(
                model=model,
                base_url=ARGO_BASE_URL,
                api_key="argo",  # gateway ignores the key; auth is the user field
                temperature=temperature,
                # Argo requires the ANL username in the request body.
                extra_body={"user": argo_user},
            )
            _CHAT_MODEL_CACHE[key] = chat
        return chat

    if backend == "openai":
        from langchain_openai import ChatOpenAI

        model = os.environ.get("OPENAI_MODEL", OPENAI_MODEL)
        key = ("openai", model, temperature)
        chat = _CHAT_MODEL_CACHE.get(key)
        if chat is None:
            # api_key is read from OPENAI_API_KEY by langchain_openai; base_url
            # defaults to api.openai.com. Nothing ANL-specific here.
            chat = ChatOpenAI(model=model, temperature=temperature)
            _CHAT_MODEL_CACHE[key] = chat
        return chat

    from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline

    mid = model_id or DEFAULT_CHAT_MODEL
    key = ("local", mid, max_new_tokens)
    chat = _CHAT_MODEL_CACHE.get(key)
    if chat is None:
        pipe = HuggingFacePipeline.from_model_id(
            model_id=mid,
            task="text-generation",
            pipeline_kwargs={
                "max_new_tokens": max_new_tokens,
                "do_sample": temperature > 0,
                "return_full_text": False,
            },
        )
        chat = _AsyncChatHuggingFace(llm=pipe)
        _CHAT_MODEL_CACHE[key] = chat
    return chat


def chat(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    max_new_tokens: int = 512,
    context: Any = None,
) -> str:
    """One-shot convenience chat used by the provenance query shell.

    Builds (cached) a routed chat model via :func:`make_chat_model` and returns the
    response *text*. Routing (Argo -> OpenAI -> local HuggingFace) is identical to
    the examples. ``context`` is accepted for backward-compat and ignored -- the query
    shell is a meta-tool that translates questions to pandas, not part of a captured
    workflow, so it emits no provenance of its own.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    model = make_chat_model(max_new_tokens=max_new_tokens, temperature=temperature)
    messages: list[Any] = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    resp = model.invoke(messages)
    return resp.content if hasattr(resp, "content") else str(resp)


def _make_async_chat_hf():
    """Build the async-capable ChatHuggingFace subclass (lazily, once)."""
    from langchain_huggingface import ChatHuggingFace

    class _AsyncChatHuggingFace(ChatHuggingFace):
        """ChatHuggingFace that supports ``.ainvoke``.

        ``ChatHuggingFace`` over a local ``HuggingFacePipeline`` raises
        ``NotImplementedError`` for async generation, but the Academy LLM examples
        (06/07) drive the model through LangGraph/ReACT ``.ainvoke``. We restore the
        default ``BaseChatModel`` behavior: run the sync ``_generate`` in a thread.
        This is harness plumbing only -- no change to the model or the agent logic.
        """

        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            import asyncio
            import functools

            sync_mgr = run_manager.get_sync() if run_manager else None
            func = functools.partial(
                self._generate, messages, stop=stop, run_manager=sync_mgr, **kwargs
            )
            return await asyncio.get_running_loop().run_in_executor(None, func)

        def _to_chat_prompt(self, messages) -> str:
            # ChatHuggingFace insists the LAST message be a HumanMessage, but the
            # Academy examples legitimately end a prompt on a system/assistant
            # message (e.g. the group-chat stopping/supervisor checks send a single
            # SystemMessage) -- valid for ChatOpenAI. The tokenizer's chat template
            # handles any trailing role via add_generation_prompt=True, so we build
            # the prompt directly and drop the restriction. No semantics change.
            if not messages:
                raise ValueError("At least one message must be provided!")
            dicts = [self._to_chatml_format(m) for m in messages]
            return self.tokenizer.apply_chat_template(
                dicts, tokenize=False, add_generation_prompt=True
            )

    return _AsyncChatHuggingFace


# Built on first use of make_chat_model (keeps import of langchain_huggingface lazy).
class _AsyncChatHuggingFaceProxy:
    _cls = None

    def __call__(self, *args, **kwargs):
        if _AsyncChatHuggingFaceProxy._cls is None:
            _AsyncChatHuggingFaceProxy._cls = _make_async_chat_hf()
        return _AsyncChatHuggingFaceProxy._cls(*args, **kwargs)


_AsyncChatHuggingFace = _AsyncChatHuggingFaceProxy()
