#!/usr/bin/env python
"""Interactively query captured provenance.

Loads a Flowcept buffer (or a run directory) into a pandas DataFrame and drops you
into a REPL with helpers -- and an ``ask("...")`` function that answers **natural
language** questions by translating them to pandas with the tutorial's LLM
(Argo → vLLM → OpenAI → local CPU model, in priority order).

Usage
-----
    # interactive shell on a run dir or a buffer (defaults to the shipped sample)
    python provenance/query.py runs/06-llm_20260727-1810/
    python provenance/query.py provenance/sample/07-mol-design.jsonl
    python provenance/query.py                     # -> provenance/sample/...

    # one-shot natural-language question
    python provenance/query.py runs/07-mol-design_*/ --ask "which tasks failed and why?"

In the shell you have: ``df`` (tasks), ``records`` (raw), ``prov`` (helpers),
``pd``, and ``ask(question)``. Example queries are printed on start.

For Flowcept's own natural-language provenance agent (MCP), see the note at the
bottom of this file / the README.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from flowcept_academy import provenance as prov  # noqa: E402

# Columns worth advertising to the user / the LLM (skip the ~100 telemetry cols).
KEY_COLS = [
    "subtype", "activity_id", "agent_id", "status", "stderr",
    "started_at", "ended_at", "parent_task_id", "workflow_id", "campaign_id",
    "custom_metadata.cross_agent_call", "custom_metadata.agent_type",
    "used.call_type", "used.agent_class", "used.user_prompt",
    "generated.total_tokens", "generated.response_text",
    # LangGraph-callback llm_call records (e.g. 07) use these instead of
    # used.user_prompt / generated.response_text:
    "used.messages", "used.model", "generated.text",
]


def _resolve_buffer(path: str | None) -> str:
    """Accept a buffer file, a run dir, or None (-> shipped sample)."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not path:
        return os.path.join(here, "sample", "07-mol-design.jsonl")
    if os.path.isdir(path):
        hits = glob.glob(os.path.join(path, "**", "flowcept_buffer.jsonl"), recursive=True)
        hits += glob.glob(os.path.join(path, "*.jsonl"))
        if not hits:
            raise FileNotFoundError(f"no *.jsonl provenance buffer under {path}")
        return sorted(hits)[0]
    return path


def _elapsed(df: pd.DataFrame) -> pd.Series:
    if {"started_at", "ended_at"}.issubset(df.columns):
        return (df["ended_at"] - df["started_at"]).astype("float")
    return pd.Series(dtype="float")


# ---------------------------------------------------------------------------
# Natural-language -> pandas
# ---------------------------------------------------------------------------
_SAFE_BUILTINS = {
    "len": len, "min": min, "max": max, "sum": sum, "sorted": sorted, "round": round,
    "str": str, "int": int, "float": float, "list": list, "dict": dict, "set": set,
    "abs": abs, "any": any, "all": all, "bool": bool, "enumerate": enumerate, "range": range,
}


def make_ask(df: pd.DataFrame):
    """Return an ``ask(question)`` closure bound to this DataFrame."""
    from flowcept_academy import util as llm

    cols = [c for c in KEY_COLS if c in df.columns]
    all_cols = list(df.columns)

    def _extract(raw: str) -> str:
        expr = raw.strip()
        if "```" in expr:
            expr = expr.split("```")[1].replace("python", "", 1).strip()
        for line in expr.splitlines():
            if line.strip().startswith("df"):
                return line.strip()
        return expr.splitlines()[0].strip() if expr.splitlines() else expr

    def _translate(question: str, error: str | None = None, prev: str | None = None,
                   temperature: float = 0.0) -> str:
        system = (
            "You translate a question about a pandas DataFrame named `df` into ONE "
            "line of pandas. `df` holds provenance TASK records. Use column names "
            "EXACTLY as given, including dotted prefixes -- do NOT shorten them "
            "(e.g. `custom_metadata.agent_type`, `generated.total_tokens`, "
            "`used.user_prompt`), accessed as df['custom_metadata.agent_type']. "
            "`subtype`, `status`, `activity_id`, `agent_id` are VALUES in columns, "
            "not columns themselves -- filter with df[df['subtype'] == 'llm_call']. "
            f"Columns: {', '.join(cols)}. "
            "subtype values: academy_action, academy_lifecycle, academy_loop, llm_call, "
            "langgraph_node, langgraph_graph, tool_call. status values: FINISHED, ERROR.\n"
            "NOTE: llm_call records from LangGraph (e.g. exercise 07) store the prompt in "
            "`used.messages` and the answer in `generated.text` (NOT `used.user_prompt` / "
            "`generated.response_text`, which those records leave empty). Prefer "
            "coalescing when a column may be empty for some rows.\n"
            "Examples:\n"
            "Q: how many rows of each subtype? -> df['subtype'].value_counts()\n"
            "Q: show the langgraph_node rows -> df[df['subtype'] == 'langgraph_node']\n"
            "Q: which tasks failed and why? -> df[df['status'] == 'ERROR'][['activity_id','stderr']]\n"
            "Q: total tokens for llm calls -> df[df['subtype']=='llm_call']['generated.total_tokens'].sum()\n"
            "Return ONLY a single pandas expression starting with `df` -- no prose."
        )
        q = question
        if error and prev:
            # self-heal: feed the failing expression + error + full column list back
            q = (f"Your previous pandas expression failed.\nExpression: {prev}\n"
                 f"Error: {error}\nExact available columns: {', '.join(all_cols)}\n"
                 f"Return a corrected single pandas expression for: {question}")
        return _extract(llm.chat(q, system=system, temperature=temperature,
                                 context={"tool": "provenance-query"}))

    def ask(question: str, show_code: bool = True, retries: int = 1):
        expr = _translate(question)
        last_err = None
        for attempt in range(retries + 1):
            if show_code:
                print(f">>> {expr}")
            try:
                result = eval(expr, {"__builtins__": _SAFE_BUILTINS},
                              {"df": df, "pd": pd, "prov": prov})
                if isinstance(result, pd.DataFrame):
                    disp = result
                    if result.shape[1] > 12:  # project wide results to readable key columns
                        keep = [c for c in KEY_COLS if c in result.columns]
                        disp = result[keep] if keep else result.iloc[:, :12]
                    print(disp.head(20).to_string())
                elif isinstance(result, pd.Series):
                    print(result.head(20).to_string())
                else:
                    print(result)
                return result
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                if attempt < retries:
                    print(f"   (failed: {last_err} -- retrying)")
                    expr = _translate(question, error=last_err, prev=expr, temperature=0.4)
        print(f"(could not run the generated query: {last_err})")
        print("Try rephrasing, or write pandas directly on `df` "
              "(tip: dotted columns like df['custom_metadata.agent_type']).")
        return None

    return ask


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------
def _relevant_questions(records):
    """Identify which example produced this buffer (by workflow name) so the
    shell can label the suggested questions. Questions themselves are generic;
    each exercise's README lists ones tailored to it."""
    for r in records:
        if r.get("type") == "workflow" and r.get("name"):
            return str(r["name"]), []
    return None, []


_GENERIC_Q = [
    "which tasks failed and why?",
    "how many tasks of each subtype?",
    "how many LLM calls per agent and total tokens?",
]

BANNER = """\
Provenance query shell
----------------------
loaded: {buf}
records: {n} ({tasks} tasks, {wf} workflows)   backend for ask(): {backend}

In scope:  df (tasks)  ·  records (raw)  ·  prov (helpers)  ·  pd  ·  ask("...")

Natural language{relevant_for}:
{nl}

Direct pandas / helpers:
    df["subtype"].value_counts()
    df[df.status == "ERROR"][["activity_id","stderr"]]
    df[df.subtype == "llm_call"][["used.call_type","generated.total_tokens"]]
    prov.print_tailored(records)     # tailored, content-aware analysis
    prov.llm_summary(df)             # tokens per agent
    prov.print_lineage(prov.load_buffer(BUF))
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactively query captured provenance.")
    ap.add_argument("path", nargs="?", default=None, help="buffer .jsonl or a run dir")
    ap.add_argument("--ask", metavar="Q", default=None, help="one-shot NL question, then exit")
    args = ap.parse_args()

    buf = _resolve_buffer(args.path)
    df = prov.tasks(prov.load_buffer(buf))
    records = prov.load_records(buf)
    ask = make_ask(df)

    if args.ask:
        ask(args.ask)
        return 0

    from flowcept_academy import util as llm
    ex_id, questions = _relevant_questions(records)
    questions = questions or _GENERIC_Q
    nl = "\n".join(f'    ask("{q}")' for q in questions)
    banner = BANNER.format(buf=buf, n=len(records), tasks=len(df),
                           wf=sum(1 for r in records if r.get("type") == "workflow"),
                           backend=llm.which_backend(),
                           relevant_for=(f" (relevant to {ex_id})" if ex_id else ""),
                           nl=nl)
    ns = {"df": df, "records": records, "prov": prov, "pd": pd, "ask": ask, "BUF": buf}
    try:
        from IPython import start_ipython  # nicer shell if available
        print(banner)
        start_ipython(argv=[], user_ns=ns)
    except Exception:
        import code
        code.interact(banner=banner, local=ns, exitmsg="bye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------------------------------------------------------------------
# Flowcept's OWN natural-language provenance agent (MCP), for reference:
#   flowcept --start-agent            # starts the MCP server
#   flowcept --start-agent-gui        # Streamlit GUI
#   # or, in Python, over a buffer:
#   from flowcept.agents.flowcept_agent import FlowceptAgent
#   FlowceptAgent(buffer_path="flowcept_buffer.jsonl")
# It plans + generates pandas over your records using an external LLM.
# ---------------------------------------------------------------------------
