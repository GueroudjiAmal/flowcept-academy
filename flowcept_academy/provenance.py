"""Provenance loading, querying, and analysis helpers.

This module is the analysis toolkit for the tutorial. It reads the provenance
that the Flowcept Academy plugin captures -- either from the offline JSONL buffer
(``flowcept_buffer.jsonl``, the default, no services needed) or from MongoDB via
``Flowcept.db`` -- and turns it into pandas DataFrames, lineage trees, summaries,
and charts.

Record model (recap)
--------------------
Flowcept emits two kinds of records, distinguished by the top-level ``type``:

* ``workflow`` -- one per run (the campaign's top-level workflow) plus one
  *sub-workflow* per Academy agent (``name`` = ``"<AgentType>:<AgentId>"``,
  ``parent_workflow_id`` -> the top-level workflow).
* ``task`` -- everything else, distinguished by ``subtype``:
    - ``academy_lifecycle``  agent_startup / agent_shutdown
    - ``academy_action``     one per ``@action`` invocation
    - ``academy_loop``       one per ``@loop`` start/exit
    - ``llm_call``           one per LLM call (``parent_task_id`` -> its action)

Lineage keys: ``campaign_id`` -> ``workflow_id`` -> ``task_id`` <- ``parent_task_id``.

Everything here is **terminal-only**: summaries, lineage trees, a tailored
content-aware analysis, and a text dashboard (ASCII bars). No matplotlib, no image
files -- so it runs unchanged over SSH on an Aurora compute node.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd

DEFAULT_BUFFER = "flowcept_buffer.jsonl"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_buffer(path: str = DEFAULT_BUFFER) -> pd.DataFrame:
    """Load a Flowcept JSONL provenance buffer into a DataFrame (one row/record).

    Tries ``Flowcept.read_buffer_file`` first (handles Flowcept's own conventions)
    and falls back to a plain line-by-line JSON read so the tutorial works with
    any buffer file, wherever it came from.
    """
    try:
        from flowcept import Flowcept

        # cleanup_files=False: never delete the buffer we are analyzing.
        records = Flowcept.read_buffer_file(path, cleanup_files=False)
        if isinstance(records, list) and records:
            return pd.json_normalize(records)
    except Exception:
        pass

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Provenance buffer not found: {path!r}. Run a captured workflow first."
        )
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return pd.json_normalize(rows)


def load_from_db(campaign_id: str | None = None, workflow_id: str | None = None) -> pd.DataFrame:
    """Load provenance tasks from MongoDB via ``Flowcept.db`` (online mode).

    Requires MongoDB enabled in ``settings.yaml`` and a run that persisted there.
    """
    from flowcept import Flowcept

    filt: dict[str, Any] = {}
    if campaign_id:
        filt["campaign_id"] = campaign_id
    if workflow_id:
        filt["workflow_id"] = workflow_id
    tasks = Flowcept.db.query(filter=filt or None, collection="tasks")
    return pd.json_normalize(tasks or [])


# ---------------------------------------------------------------------------
# Slicing helpers
# ---------------------------------------------------------------------------
def workflows(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the workflow records."""
    if "type" not in df.columns:
        return df.iloc[0:0]
    return df[df["type"] == "workflow"].copy()


def tasks(df: pd.DataFrame, subtype: str | None = None) -> pd.DataFrame:
    """Return task records, optionally filtered to one ``subtype``.

    Some interceptors (e.g. the LangGraph plugin) emit task records without a
    ``type`` field, so we treat any non-workflow record that carries a ``subtype``
    as a task too -- otherwise cross-framework records would be invisible.
    """
    if "type" not in df.columns:
        out = df.copy()
    else:
        is_task = df["type"] == "task"
        if "subtype" in df.columns:
            is_task = is_task | (df["type"].isna() & df["subtype"].notna())
        out = df[is_task].copy()
    if subtype is not None and "subtype" in out.columns:
        out = out[out["subtype"] == subtype].copy()
    return out


def _eq(df: pd.DataFrame, col: str, value: Any) -> pd.Series:
    """Column-safe equality mask.

    ``df.get(col) == value`` collapses to the scalar ``False`` when ``col`` is
    absent (``df.get`` returns ``None``), and ``df[False]`` then raises
    ``KeyError: False``. This always returns a proper boolean Series aligned to
    ``df.index`` -- all-``False`` when the column is missing.
    """
    if col in df.columns:
        return df[col] == value
    return pd.Series(False, index=df.index)


def _elapsed_seconds(df: pd.DataFrame) -> pd.Series:
    if {"started_at", "ended_at"}.issubset(df.columns):
        return (df["ended_at"] - df["started_at"]).astype("float")
    return pd.Series([float("nan")] * len(df), index=df.index)


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------
def summary(df: pd.DataFrame) -> dict[str, Any]:
    """Compute a compact overview dict of the whole provenance graph."""
    wfs = workflows(df)
    tks = tasks(df)
    out: dict[str, Any] = {
        "records": int(len(df)),
        "workflows": int(len(wfs)),
        "tasks": int(len(tks)),
    }
    if "campaign_id" in df.columns:
        out["campaigns"] = sorted(x for x in df["campaign_id"].dropna().unique())
    if "subtype" in tks.columns:
        out["by_subtype"] = tks["subtype"].value_counts().to_dict()
    if "agent_id" in tks.columns:
        out["by_agent"] = tks["agent_id"].dropna().value_counts().to_dict()
    if "status" in tks.columns:
        out["by_status"] = tks["status"].value_counts().to_dict()
    return out


def print_summary(df: pd.DataFrame) -> None:
    """Pretty-print :func:`summary` to stdout."""
    s = summary(df)
    print("=" * 60)
    print("PROVENANCE SUMMARY")
    print("=" * 60)
    print(f"  records   : {s['records']}")
    print(f"  workflows : {s['workflows']}")
    print(f"  tasks     : {s['tasks']}")
    if s.get("campaigns"):
        print(f"  campaigns : {', '.join(str(c)[:8] for c in s['campaigns'])}")
    for title, key in [
        ("by subtype", "by_subtype"),
        ("by agent", "by_agent"),
        ("by status", "by_status"),
    ]:
        if s.get(key):
            print(f"\n  {title}:")
            for k, v in s[key].items():
                print(f"    {str(k):<28} {v}")
    print("=" * 60)


def llm_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-agent LLM call counts and token totals from ``llm_call`` records."""
    calls = tasks(df, "llm_call")
    if calls.empty:
        return pd.DataFrame(columns=["agent", "calls", "total_tokens"])
    agent_col = "used.agent_class" if "used.agent_class" in calls.columns else "agent_id"
    tok_col = "generated.total_tokens"
    if tok_col not in calls.columns:
        calls[tok_col] = pd.NA
    g = calls.groupby(calls.get(agent_col, "unknown"), dropna=False)
    out = g.agg(calls=("subtype", "size"), total_tokens=(tok_col, "sum")).reset_index()
    out = out.rename(columns={out.columns[0]: "agent"})
    return out.sort_values("calls", ascending=False).reset_index(drop=True)


def action_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-activity call counts and mean/total elapsed time for actions."""
    acts = tasks(df, "academy_action")
    if acts.empty:
        return pd.DataFrame(columns=["activity_id", "count", "mean_s", "total_s"])
    acts = acts.copy()
    acts["_elapsed"] = _elapsed_seconds(acts)
    g = acts.groupby("activity_id")
    out = g.agg(
        count=("activity_id", "size"),
        mean_s=("_elapsed", "mean"),
        total_s=("_elapsed", "sum"),
    ).reset_index()
    return out.sort_values("count", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------
def lineage_edges(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Return provenance edges as ``(parent, child, relation)`` triples.

    Relations: ``workflow`` (top -> agent sub-workflow), ``task`` (workflow ->
    action/loop/lifecycle), ``spawns`` (action -> child llm_call via
    ``parent_task_id``).
    """
    edges: list[tuple[str, str, str]] = []
    wfs = workflows(df)
    for _, r in wfs.iterrows():
        parent = r.get("parent_workflow_id")
        if isinstance(parent, str) and parent:
            edges.append((parent, r["workflow_id"], "workflow"))
    tks = tasks(df)
    for _, r in tks.iterrows():
        tid = r.get("task_id")
        wf = r.get("workflow_id")
        ptid = r.get("parent_task_id")
        if isinstance(ptid, str) and ptid:
            edges.append((ptid, tid, "spawns"))
        elif isinstance(wf, str) and wf and isinstance(tid, str):
            edges.append((wf, tid, "task"))
    return edges


def print_lineage(df: pd.DataFrame, max_children: int = 40) -> None:
    """Print an indented lineage tree: campaign -> agents -> actions -> llm_calls."""
    wfs = workflows(df)
    tks = tasks(df)
    top = wfs[wfs.get("parent_workflow_id").isna()] if "parent_workflow_id" in wfs.columns else wfs
    agent_wfs = wfs[~wfs.index.isin(top.index)] if not top.empty else wfs.iloc[0:0]

    def label(r):
        return r.get("name") or str(r.get("workflow_id", ""))[:8]

    for _, twf in top.iterrows():
        print(f"campaign {str(twf.get('campaign_id',''))[:8]}  workflow: {label(twf)}")
        kids = agent_wfs[_eq(agent_wfs, "parent_workflow_id", twf["workflow_id"])]
        for _, awf in kids.iterrows():
            print(f"  └─ agent workflow: {label(awf)}")
            acts = tks[
                _eq(tks, "workflow_id", awf["workflow_id"])
                & _eq(tks, "subtype", "academy_action")
            ]
            for _, act in acts.head(max_children).iterrows():
                st = act.get("status", "")
                print(f"       ├─ action: {act.get('activity_id')}  [{st}]")
                calls = tks[_eq(tks, "parent_task_id", act.get("task_id"))]
                for _, c in calls.iterrows():
                    print(f"       │    └─ llm_call: {c.get('activity_id')}")


# ---------------------------------------------------------------------------
# Performance / overhead
# ---------------------------------------------------------------------------
def load_perf(path: str) -> pd.DataFrame:
    """Load a ``provenance_perf_*.csv`` overhead file written by the plugin.

    Multi-process runs (make_process_executor) can append duplicate header rows to
    the same perf CSV, so we coerce ``elapsed_us`` to numeric and drop the bad rows.
    """
    df = pd.read_csv(path)
    if "elapsed_us" in df.columns:
        df["elapsed_us"] = pd.to_numeric(df["elapsed_us"], errors="coerce")
        df = df.dropna(subset=["elapsed_us"])
    return df


def perf_summary(perf: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the raw per-event overhead CSV into per-category statistics."""
    g = perf.groupby("category")["elapsed_us"]
    out = g.agg(n="size", total_ms=lambda s: s.sum() / 1000.0, mean_us="mean", max_us="max")
    return out.reset_index().sort_values("total_ms", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Terminal dashboard (ASCII bars -- no matplotlib, no image files)
# ---------------------------------------------------------------------------
def _has_llm_tokens(df: pd.DataFrame) -> bool:
    s = llm_summary(df)
    return (not s.empty) and (s["total_tokens"].fillna(0).sum() > 0)


def _bar_rows(pairs: list[tuple[str, float]], width: int = 32, label_w: int = 22) -> None:
    """Print ``label | ####### value`` rows scaled to the largest value."""
    if not pairs:
        print("    (none)")
        return
    top = max((v for _, v in pairs), default=0) or 1
    for name, val in pairs:
        n = int(round(width * val / top)) if top else 0
        bar = "█" * n if n else "▏"
        num = f"{val:g}" if float(val).is_integer() else f"{val:.2f}"
        print(f"    {str(name)[:label_w]:<{label_w}} │ {bar:<{width}} {num}")


def text_dashboard(df: pd.DataFrame, perf: pd.DataFrame | None = None,
                   title: str = "Academy x Flowcept -- provenance dashboard") -> None:
    """Print a content-aware provenance dashboard as text (terminal-only).

    Panel 1: records by subtype. Panel 2 adapts -- **LLM tokens by agent** when the
    example made LLM calls, else **tasks by activity** (more informative for the
    actor/loop/multi-process examples). Panel 3 (optional): capture overhead. No
    images are written, so it works over SSH on a compute node.
    """
    tks = tasks(df)
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

    print("\n  records by subtype:")
    counts = (tks["subtype"].value_counts() if "subtype" in tks.columns
              else pd.Series(dtype=int))
    _bar_rows([(k, float(v)) for k, v in counts.items()])

    if _has_llm_tokens(df):
        print("\n  LLM tokens by agent:")
        summ = llm_summary(df)
        _bar_rows([(a, float(t or 0)) for a, t in
                   zip(summ["agent"], summ["total_tokens"].fillna(0))])
    else:
        print("\n  tasks by activity:")
        acnt = (tks["activity_id"].value_counts() if "activity_id" in tks.columns
                else pd.Series(dtype=int))
        _bar_rows([(k, float(v)) for k, v in acnt.items()])

    if perf is not None and not perf.empty:
        print("\n  capture overhead (total ms by category):")
        ps = perf_summary(perf)
        _bar_rows([(c, float(m)) for c, m in zip(ps["category"], ps["total_ms"])])
    print("=" * 60)


# Back-compat alias: older callers used ``dashboard(...)``; it is now text-only.
def dashboard(df: pd.DataFrame, perf: pd.DataFrame | None = None,
              title: str = "Academy x Flowcept -- provenance dashboard", **_ignored) -> None:
    """Deprecated PNG dashboard -> now the terminal :func:`text_dashboard`."""
    text_dashboard(df, perf=perf, title=title)


# ---------------------------------------------------------------------------
# Flowcept's built-in provenance cards / reports
# ---------------------------------------------------------------------------
def provenance_card(buffer_path: str, out_dir: str = ".", stem: str | None = None) -> dict[str, str]:
    """Generate Flowcept's built-in **provenance card** (markdown).

    Uses ``Flowcept.generate_report`` -- the report feature shipped in Flowcept --
    to produce, from a captured buffer, ``<stem>_card.md``: the ``provenance_card``
    (markdown -- workflow diagram, counts, timing tables, insights). Markdown keeps
    the whole toolkit terminal-only (``cat`` it, or read it in any viewer); no PDF /
    image deps needed. Returns the path written.
    """
    from collections import Counter

    from flowcept import Flowcept

    stem = stem or os.path.splitext(os.path.basename(buffer_path))[0]
    os.makedirs(out_dir, exist_ok=True)
    out: dict[str, str] = {}

    # Flowcept's card aggregates a SINGLE workflow, but an agentic run has several
    # (a Flowcept controller workflow + per-plugin/per-agent sub-workflows), and the
    # tasks live under the plugin workflows -- so a naive card lands on the empty
    # controller workflow. We build a flattened single-workflow *reporting view*:
    # all task records (incl. LangGraph records that carry no `type`) re-homed under
    # the workflow most tasks reference, so the card summarizes the whole run.
    recs = load_records(buffer_path)
    task_recs = [r for r in recs
                 if r.get("type") == "task" or (r.get("type") is None and r.get("subtype"))]
    wf_recs = [r for r in recs if r.get("type") == "workflow"]
    records = None
    if task_recs and wf_recs:
        counts = Counter(r.get("workflow_id") for r in task_recs if r.get("workflow_id"))
        main_id = counts.most_common(1)[0][0] if counts else wf_recs[0].get("workflow_id")
        main_wf = next((w for w in wf_recs if w.get("workflow_id") == main_id), wf_recs[0])
        flat = []
        for t in task_recs:
            t = dict(t)
            t["type"] = "task"
            t["workflow_id"] = main_id
            flat.append(t)
        records = [dict(main_wf)] + flat

    def _gen(report_type, fmt, output_path):
        if records is not None:
            Flowcept.generate_report(report_type=report_type, format=fmt,
                                     records=records, output_path=output_path)
        else:
            Flowcept.generate_report(report_type=report_type, format=fmt,
                                     input_jsonl_path=buffer_path, output_path=output_path)

    md = os.path.join(out_dir, f"{stem}_card.md")
    _gen("provenance_card", "markdown", md)
    out["markdown"] = md
    print(f"provenance card -> {md}")
    return out


# ---------------------------------------------------------------------------
# Tailored, content-aware analysis
# ---------------------------------------------------------------------------
# The generic summary/dashboard fit every example, but each stock example
# exercises a *different* slice of the provenance model. These helpers inspect
# the raw records and report only what a given example actually produced, so the
# analysis is tailored to that example:
#
#   actions/state (01, 05) · loop events (02) · cross-agent calls (03, 06, 08) ·
#   cross-process lineage (04) · LLM calls with prompts/tokens (06, 08) ·
#   multi-agent conversation (08)
# ---------------------------------------------------------------------------
def load_records(path: str = DEFAULT_BUFFER) -> list[dict[str, Any]]:
    """Load a buffer as raw record dicts (nested fields intact, unlike the DataFrame)."""
    try:
        from flowcept import Flowcept

        recs = Flowcept.read_buffer_file(path, cleanup_files=False)
        if isinstance(recs, list) and recs:
            return recs
    except Exception:
        pass
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def _clip(v: Any, n: int = 70) -> str:
    s = str(v).replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def print_tailored(records: list[dict[str, Any]]) -> list[str]:
    """Print the analysis relevant to whatever this example captured.

    Returns the list of section names emitted (handy for tests/summaries).
    """
    # Treat non-workflow records with a subtype as tasks too (e.g. LangGraph
    # plugin records carry a subtype but no explicit type field).
    tks = [r for r in records
           if r.get("type") == "task" or (r.get("type") is None and r.get("subtype"))]
    by_id = {t.get("task_id"): t for t in tks}
    emitted: list[str] = []

    def act_of(tid):
        t = by_id.get(tid)
        return t.get("activity_id") if t else None

    print("\n" + "-" * 64)
    print("TAILORED ANALYSIS  (only what this example produced)")
    print("-" * 64)

    # --- failures / errors (surfaced first -- this is where provenance shines) ---
    errors = [t for t in tks
              if str(t.get("status", "")).upper() == "ERROR" or t.get("stderr")]
    if errors:
        emitted.append("failures")
        print("\n⚠  Failures captured (status=ERROR) -- provenance records what broke:")
        for t in errors:
            print(f"    {t.get('subtype')}/{t.get('activity_id')}  "
                  f"[{t.get('status')}]  stderr: {_clip(t.get('stderr'), 70)}")

    # --- actions + state / outputs (every example has actions) ---------------
    acts = sorted((t for t in tks if t.get("subtype") == "academy_action"),
                  key=lambda t: t.get("started_at", 0))
    if acts:
        emitted.append("actions")
        print("\n• Actions (in order)  activity  [agent]  used -> generated")
        for t in acts:
            agent = (t.get("custom_metadata") or {}).get("agent_type", "?")
            used = t.get("used")
            gen = t.get("generated")
            print(f"    {t.get('activity_id'):<22} [{agent}]  "
                  f"{_clip(used, 40)} -> {_clip(gen, 40)}")

    # --- loop events (02) ---------------------------------------------------
    loops = [t for t in tks if t.get("subtype") == "academy_loop"]
    if loops:
        emitted.append("loops")
        print("\n• Loop events (autonomous @loop; grouped by group_id)")
        for t in sorted(loops, key=lambda t: t.get("started_at", 0)):
            ev = (t.get("custom_metadata") or {}).get("loop_event")
            print(f"    {t.get('activity_id'):<16} event={ev:<6} group={str(t.get('group_id'))[:8]}")

    # --- cross-agent calls (03, 06, 08) -------------------------------------
    xcalls = [t for t in acts if (t.get("custom_metadata") or {}).get("cross_agent_call")]
    if xcalls:
        emitted.append("cross_agent")
        print("\n• Cross-agent calls  (caller -> callee.action)")
        for t in xcalls:
            cm = t.get("custom_metadata") or {}
            src = cm.get("source_agent_id", "?")
            print(f"    {str(src)[:22]} -> {t.get('activity_id')} "
                  f"[{cm.get('agent_type','?')} {str(t.get('agent_id'))[:16]}]")

    # --- multi-process execution (04) ---------------------------------------
    # An action that offloaded work to a process pool returns a list of results,
    # each recording the pid/host it ran on. Surface where the work executed.
    mp_rows: list[tuple[str, list]] = []
    for t in acts:
        gen = t.get("generated")
        if isinstance(gen, list) and gen and all(
            isinstance(x, dict) and "pid" in x for x in gen
        ):
            mp_rows.append((t.get("activity_id"), gen))
    if mp_rows:
        emitted.append("multi_process")
        print("\n• Multi-process execution  (action -> work run in separate worker processes)")
        for activity, gen in mp_rows:
            pids = sorted({x.get("pid") for x in gen})
            hosts = sorted({x.get("host") for x in gen if x.get("host")})
            print(f"    {activity}: {len(gen)} results across {len(pids)} worker "
                  f"process(es) pids={pids} host(s)={hosts}")
            for x in gen:
                print(f"        pid {x.get('pid')} host {x.get('host')}  {_clip(x, 46)}")

    # --- cross-framework: LangGraph nodes (07) ------------------------------
    lg_nodes = [t for t in tks if t.get("subtype") in ("langgraph_node", "langgraph_graph")]
    if lg_nodes:
        emitted.append("langgraph")
        print("\n• Cross-framework: LangGraph graph/nodes (Academy action -> LangGraph)")
        for t in sorted(lg_nodes, key=lambda t: t.get("started_at", 0)):
            kind = "graph" if t.get("subtype") == "langgraph_graph" else "node "
            print(f"    {kind} {str(t.get('activity_id')):<16} "
                  f"group={str(t.get('group_id'))[:8]} "
                  f"{_clip(t.get('used'), 28)} -> {_clip(t.get('generated'), 28)}")
        tools = [t for t in tks if t.get("subtype") == "tool_call"]
        for t in tools:
            print(f"    tool  {t.get('activity_id')}  parent={act_of(t.get('parent_task_id'))} "
                  f"{_clip(t.get('used'), 24)} -> {_clip(t.get('generated'), 24)}")

    # --- LLM calls (06, 08) -------------------------------------------------
    llms = sorted((t for t in tks if t.get("subtype") == "llm_call"),
                  key=lambda t: t.get("started_at", 0))
    if llms:
        emitted.append("llm")
        print("\n• LLM calls  (call_type [agent] tokens; parent action; prompt -> response)")
        for t in llms:
            u = t.get("used") or {}
            g = t.get("generated") or {}
            ctype = u.get("call_type") or t.get("activity_id")
            agent = u.get("agent_class") or (u.get("ctx_agent"))
            parent = act_of(t.get("parent_task_id"))
            model = u.get("model_used") or u.get("model")
            print(f"    {ctype:<10} [{agent}]  tokens={g.get('total_tokens')} "
                  f"model={model}  parent={parent}")
            print(f"        prompt : {_clip(u.get('user_prompt'), 80)}")
            print(f"        answer : {_clip(g.get('response_text'), 80)}")

    # --- multi-agent conversation (08: several 'respond' llm calls) ----------
    responds = [t for t in llms if (t.get("used") or {}).get("call_type") == "respond"]
    if len(responds) > 1:
        emitted.append("conversation")
        print("\n• Conversation transcript  (turn order across participants)")
        for i, t in enumerate(responds, 1):
            u = t.get("used") or {}
            g = t.get("generated") or {}
            print(f"    turn {i}  {u.get('ctx_agent') or u.get('agent_class')}: "
                  f"{_clip(g.get('response_text'), 80)}")

    print("-" * 64)
    return emitted


if __name__ == "__main__":
    import sys

    buf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BUFFER
    d = load_buffer(buf)
    print_summary(d)
    print()
    print_lineage(d)
    print_tailored(load_records(buf))
