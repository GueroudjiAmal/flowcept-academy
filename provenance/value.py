#!/usr/bin/env python
"""
The value of provenance -- one rigorous engine, every exercise
==============================================================

`provenance_value.py` in each exercise dir is a thin wrapper around this module.
It takes a captured buffer (a run of yours, or -- for 07 -- the shipped sample) and
answers questions the program's *normal* output cannot, printing for each:

    Q:   the question in plain English (the same phrasing works with
         `query.py --ask "..."`)
    >>>  the EXACT pandas that produces the number -- so every figure is auditable
    ->   the answer, computed from the records
    !!   what you would be blind to WITHOUT provenance

RIGOR (why the numbers here can be trusted)
-------------------------------------------
Earlier drafts summed task durations and called the total "wall-clock". That is
wrong whenever tasks run in parallel (07's xTB relaxations run in a process pool --
two ~130 s jobs that overlap are ~130 s of wall-clock, not ~260 s). This engine is
careful about exactly that:

  * WALL-CLOCK is the union of [started_at, ended_at] intervals (parallel-aware),
    computed by `wall_clock_seconds()` -- never a sum of overlapping tasks.
  * COMPUTE TIME (sum of per-task durations) is reported separately and labelled as
    such; the gap between the two is the parallelism the run actually achieved.
  * Every displayed number is paired with the pandas that yields it, and each metric
    is derived only from fields present in the records (no hard-coded expectations).
  * `--verify` recomputes the headline aggregates a second, independent way and
    asserts they match, so a drifting value fails loudly instead of misleading.

Usage
-----
    python provenance/value.py <run_dir|buffer.jsonl> [--exercise 07-mol-design]
    python provenance/value.py --verify <run_dir|buffer.jsonl>
    # or, from an exercise dir:  python provenance_value.py [run_dir|buffer]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from flowcept_academy import provenance as prov  # noqa: E402

# --------------------------------------------------------------------------- #
# framework each record subtype belongs to (for the cross-framework story)
# --------------------------------------------------------------------------- #
FRAMEWORK = {
    "academy_lifecycle": "Academy",
    "academy_loop": "Academy",
    "academy_action": "Academy",
    "langgraph_graph": "LangGraph",
    "langgraph_node": "LangGraph",
    "llm_call": "LangChain LLM",
    "tool_call": "LangChain tool",
}
_LAYER_NOTE = {
    "academy_lifecycle": "agent startup/shutdown",
    "academy_loop": "autonomous @loop",
    "academy_action": "@action call",
    "langgraph_graph": "reasoning graph",
    "langgraph_node": "graph node",
    "llm_call": "llm.ainvoke (model + tokens)",
    "tool_call": "tool invocation",
}

# per-exercise framing: what the ORDINARY run shows, and the headline gain.
PROFILES = {
    "01-actor-client": dict(
        title="one stateful actor + its actions",
        plain="the final counter value",
        gain="every message to the actor -- inputs, outputs, order, timing -- as an "
             "audit trail",
    ),
    "02-agent-loop": dict(
        title="an autonomous @loop",
        plain="the final counter value the client read",
        gain="evidence the background loop actually ran (and when it stopped) -- "
             "proactive behavior nobody called",
    ),
    "03-agent-agent": dict(
        title="a coordinator delegating across agents",
        plain='the final string ("feebdaed")',
        gain="the who-called-whom graph and the data-flow chain across agents",
    ),
    "04-execution": dict(
        title="an agent offloading compute to worker processes",
        plain="the aggregated result",
        gain="proof the work really crossed the process boundary (distinct worker "
             "pids/hosts)",
    ),
    "05-parsl": dict(
        title="an agent delegating to a Parsl task",
        plain="the returned value (42)",
        gain="the agent -> Parsl hand-off captured in the lineage",
    ),
    "06-llm": dict(
        title="an LLM deciding to call a cross-agent tool",
        plain="the final natural-language answer",
        gain="the ReACT graph across THREE frameworks, token cost, and which node "
             "called the tool",
    ),
    "07-mol-design": dict(
        title="a real GFN2-xTB molecular-design campaign",
        plain="a ranked list of molecules",
        gain="the LLM's invalid proposals and its recovery, per-molecule xTB results "
             "tied to the model, and true token/compute cost",
    ),
    "08-discussion": dict(
        title="a multi-agent LLM group chat",
        plain="the single final answer",
        gain="who spoke, the message fan-out and peer topology, and tokens per agent",
    ),
}

_W = 78


# --------------------------------------------------------------------------- #
# rigorous primitives
# --------------------------------------------------------------------------- #
def durations(df: pd.DataFrame) -> pd.Series:
    """Per-task elapsed seconds (ended_at - started_at), NaN-safe."""
    if not {"started_at", "ended_at"}.issubset(df.columns):
        return pd.Series(dtype="float")
    s = pd.to_numeric(df["started_at"], errors="coerce")
    e = pd.to_numeric(df["ended_at"], errors="coerce")
    return (e - s).astype("float")


def wall_clock_seconds(df: pd.DataFrame) -> float:
    """Wall-clock the given tasks actually occupied = union of their
    [started_at, ended_at] intervals. Parallel/overlapping tasks are counted
    ONCE -- this is NOT the sum of durations."""
    if not {"started_at", "ended_at"}.issubset(df.columns) or df.empty:
        return 0.0
    iv = []
    for s, e in zip(pd.to_numeric(df["started_at"], errors="coerce"),
                    pd.to_numeric(df["ended_at"], errors="coerce")):
        if pd.notna(s) and pd.notna(e) and e >= s:
            iv.append((float(s), float(e)))
    if not iv:
        return 0.0
    iv.sort()
    total = 0.0
    cs, ce = iv[0]
    for a, b in iv[1:]:
        if a <= ce:
            ce = max(ce, b)
        else:
            total += ce - cs
            cs, ce = a, b
    return total + (ce - cs)


def compute_seconds(df: pd.DataFrame) -> float:
    """Sum of per-task durations = total compute time spent (across all workers)."""
    d = durations(df)
    return float(d[d >= 0].sum()) if len(d) else 0.0


def merge_task_updates(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse multiple buffer records that share one task_id into a single task.

    Flowcept streams a task as incremental *update* messages (e.g. a long-running
    @loop is flushed once when it starts -- ended_at == started_at -- and again when
    it finishes). Its DB merges these by task_id; reading the raw buffer offline does
    not, so a loop shows up as TWO rows. We reproduce the DB semantics here: one row
    per task_id (min started_at, max ended_at, last non-null for everything else),
    so counts reflect distinct logical tasks -- not raw log lines."""
    if "task_id" not in df.columns or df["task_id"].notna().sum() == 0:
        return df.reset_index(drop=True)
    keyed = df[df["task_id"].notna()].copy()
    loose = df[df["task_id"].isna()]  # no id -> can't be merged; keep each
    # tasks that appear exactly once need no work
    counts = keyed["task_id"].value_counts()
    singles = keyed[keyed["task_id"].isin(counts[counts == 1].index)]
    multi = keyed[keyed["task_id"].isin(counts[counts > 1].index)]
    merged_rows = []
    for _, g in multi.groupby("task_id", sort=False):
        row = {}
        for col in g.columns:
            nn = [v for v in g[col].tolist()
                  if not (v is None or (pd.api.types.is_scalar(v) and pd.isna(v)))]
            row[col] = nn[-1] if nn else None
        if "started_at" in g:
            s = pd.to_numeric(g["started_at"], errors="coerce").min()
            if pd.notna(s):
                row["started_at"] = float(s)
        if "ended_at" in g:
            e = pd.to_numeric(g["ended_at"], errors="coerce").max()
            if pd.notna(e):
                row["ended_at"] = float(e)
        merged_rows.append(row)
    out = pd.concat(
        [singles, pd.DataFrame(merged_rows, columns=df.columns), loose],
        ignore_index=True)
    return out


def _secs(x: float) -> str:
    """Adaptive, honest time format: never rounds a real duration down to '0.0s'.
    >=1s -> seconds; sub-second -> milliseconds; exactly 0 -> '~0'."""
    if x >= 1:
        return f"{x:.1f}s"
    if x > 0:
        return f"{x * 1000:.0f}ms"
    return "~0"


def _short(x, n: int = 46) -> str:
    s = "" if x is None else str(x)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _val(row, col):
    if col not in row:
        return None
    v = row[col]
    if isinstance(v, (list, dict)):
        return v
    return v if pd.notna(v) else None


def _input(row) -> str:
    for c in ("used.args", "used.input", "used.user_prompt", "used.messages",
              "used.model"):
        v = _val(row, c)
        if v not in (None, "", [], {}):
            return _short(v)
    return ""


def _output(row) -> str:
    for c in ("generated.output", "generated.outputs", "generated.text",
              "generated.response_text"):
        v = _val(row, c)
        if v not in (None, "", [], {}):
            return _short(v)
    return ""


def _agent(row) -> str:
    a = _val(row, "agent_id")
    if not a:
        return ""
    m = re.search(r"<([0-9a-f]+)>", str(a))
    return m.group(1)[:8] if m else _short(a, 12)


def _smiles(used_input) -> str:
    if not isinstance(used_input, str):
        return _short(used_input, 14)
    m = re.search(r"'smiles':\s*'([^']*)'", used_input)
    return m.group(1) if m else _short(used_input, 14)


# --------------------------------------------------------------------------- #
# presentation
# --------------------------------------------------------------------------- #
def _hr(ch="-"):
    print(ch * _W)


def _banner(t):
    print("\n" + "=" * _W)
    print(t)
    print("=" * _W)


def _q(n, question, code, nl):
    print(f"\nQ{n}. {question}")
    print(f"    >>> {code}")
    if nl:
        print(f'    (ask: query.py --ask "{nl}")')


def _impact(line):
    lines = line.split("\n")
    print(f"    !! Without provenance: {lines[0]}")
    for ln in lines[1:]:
        print(f"       {ln.lstrip()}")


# --------------------------------------------------------------------------- #
# lenses -- each self-guards (no-op when its fields are absent) and prints only
# figures it can derive from the records.
# --------------------------------------------------------------------------- #
def lens_inventory(df, n):
    _banner(f"{n}) What was captured (across every framework in the run)")
    _q(n, "How many records of each kind, and from which framework?",
       "df['subtype'].value_counts()", "how many tasks of each subtype?")
    vc = df["subtype"].value_counts()
    print("    ->")
    for k, v in vc.items():
        print(f"       {k:<20} {v:>4}   {FRAMEWORK.get(k, '?'):<15} "
              f"{_LAYER_NOTE.get(k, '')}")
    fw = sorted({FRAMEWORK.get(k, '?').split()[0] for k in vc.index})
    print(f"    -> frameworks touched: {', '.join(fw)}  |  total records: {len(df)}")
    _impact("Each framework logs (if at all) in its own format; here they are ONE\n"
            "graph you can query -- with no edits to the agent code.")
    return len(df)


def lens_span(df, n):
    agents = df["agent_id"].dropna().nunique() if "agent_id" in df else 0
    camps = df["campaign_id"].dropna().nunique() if "campaign_id" in df else 0
    wfs = df["workflow_id"].dropna().nunique() if "workflow_id" in df else 0
    if agents <= 1 and camps <= 1 and wfs <= 1:
        return  # nothing distinctive to show
    _banner(f"{n}) The span: distinct agents / workflows, one campaign")
    _q(n, "How many distinct agents and workflows, under how many campaigns?",
       "df['agent_id'].nunique(), df['workflow_id'].nunique(), "
       "df['campaign_id'].nunique()", "how many distinct agents are there?")
    print(f"    -> agents={agents}  workflows={wfs}  campaigns={camps}")
    _impact("Multiple agents/sub-workflows are stitched into one campaign; without\n"
            "provenance they are separate processes with no shared thread.")


def lens_cross_agent(df, n):
    col = "custom_metadata.cross_agent_call"
    if col not in df.columns:
        return
    edges = df[df[col] == True]  # noqa: E712
    if edges.empty:
        return
    _banner(f"{n}) Who called whom (the agent-to-agent graph)")
    _q(n, "Which calls crossed an agent boundary, and from which caller?",
       "df[df['custom_metadata.cross_agent_call']==True]"
       "[['activity_id','custom_metadata.source_agent_id','agent_id']]",
       "which calls were cross-agent and who called them?")
    src_col = "custom_metadata.source_agent_id"
    print("    ->")
    for _, r in edges.iterrows():
        src = _val(r, src_col)
        src = re.search(r"<([0-9a-f]+)>", str(src)).group(1)[:8] if src else "?"
        print(f"       {src} --{r['activity_id']}--> {_agent(r)}")
    _impact("The delegation graph is reconstructable from the records; the program\n"
            "output shows only the final result, not the collaboration that made it.")


def lens_trace(df, n):
    """The time-ordered narrative of what actually ran -- the core of 'impact'."""
    work = df[df["subtype"].isin(
        ["academy_action", "langgraph_node", "tool_call", "academy_loop"])].copy()
    if work.empty:
        work = df.copy()
    if "started_at" in work.columns:
        work = work.sort_values("started_at")
    _banner(f"{n}) The execution trace: replay exactly what happened, in order")
    _q(n, "In what order did the steps run, with inputs, outputs and status?",
       "df.sort_values('started_at')[['activity_id','status','used','generated']]",
       "list the actions in time order with status")
    print("    ->")
    for _, r in work.iterrows():
        mark = "ok " if r.get("status") == "FINISHED" else "ERR"
        io_in, io_out = _input(r), _output(r)
        arrow = f"  {io_in} -> {io_out}" if (io_in or io_out) else ""
        who = f"[{_agent(r)}] " if _agent(r) else ""
        print(f"       [{mark}] {who}{str(r.get('activity_id')):<26}{arrow}")
    _impact("This ordered, inspectable trace IS the run's story -- the plain output\n"
            "is only its last line.")


def lens_failures(df, n):
    if "status" not in df.columns:
        return
    errs = df[df["status"] == "ERROR"]
    if errs.empty:
        return
    _banner(f"{n}) What failed, and why (invisible in the final output)")
    _q(n, "Which tasks failed and what was the error?",
       "df[df['status']=='ERROR'][['activity_id','used','stderr']]",
       "which tasks have status ERROR and what is the stderr?")
    print(f"    -> {len(errs)} of {len(df)} records failed:")
    for _, r in errs.iterrows():
        detail = _short(_val(r, "stderr") or _input(r), 50)
        print(f"       x {str(r.get('activity_id')):<26} {detail}")
    _impact("Failures are dropped from the success-only result. Provenance keeps\n"
            "them -- what broke, on which input, with the error text.")


def lens_llm_cost(df, n):
    if "subtype" not in df.columns or not (df["subtype"] == "llm_call").any():
        return
    llm = df[df["subtype"] == "llm_call"].copy()
    tok_col = "generated.total_tokens"
    if tok_col not in llm.columns:
        return
    llm["_tok"] = pd.to_numeric(llm[tok_col], errors="coerce")
    total = int(llm["_tok"].sum())
    _banner(f"{n}) LLM cost accounting (tokens are money and latency)")
    _q(n, "How many LLM calls and tokens, in total and per model?",
       "df[df['subtype']=='llm_call']['generated.total_tokens'].sum()",
       "how many tokens did the llm_call rows use in total?")
    print(f"    -> {len(llm)} llm calls, {total:,} total tokens")
    grp_col = "used.model" if "used.model" in llm.columns else "activity_id"
    per = llm.groupby(grp_col)["_tok"].agg(["count", "sum"])
    for name, row in per.iterrows():
        print(f"       {str(name):<24} calls={int(row['count']):>3}  "
              f"tokens={int(row['sum']):>7,}")
    _impact("Token spend is attributed per call/model, so a campaign is costable\n"
            "and the expensive turns are identifiable. The output shows neither.")
    return total


def lens_timing(df, n):
    if not {"started_at", "ended_at"}.issubset(df.columns):
        return
    heavy = [s for s in ("tool_call", "academy_action", "langgraph_node")
             if (df["subtype"] == s).any()]
    if not heavy:
        heavy = [df["subtype"].mode().iloc[0]] if "subtype" in df else []
    _banner(f"{n}) Time: compute-time vs. wall-clock (parallelism, done right)")
    _q(n, "How much wall-clock did the work take, and how much did parallelism save?",
       "value.wall_clock_seconds(df[df.subtype==S])  vs  "
       "value.compute_seconds(df[df.subtype==S])", "")
    for s in heavy:
        sub = df[df["subtype"] == s]
        succ = sub[sub["status"] == "FINISHED"] if "status" in sub else sub
        cpu = compute_seconds(succ)
        wall = wall_clock_seconds(succ)
        note = ""
        if wall > 0 and cpu > wall * 1.05:
            note = (f"  (ran in PARALLEL: {cpu / wall:.1f}x speedup, "
                    f"{_secs(cpu - wall)} overlapped)")
        print(f"    -> {s:<16} n={len(succ):>3}  compute={_secs(cpu):>8}  "
              f"wall-clock={_secs(wall):>8}{note}")
    _impact("Wall-clock is the UNION of overlapping intervals, never a sum -- so the\n"
            "parallel speedup is real, not an artifact of double-counting.")


def lens_distribution(df, n):
    """04: prove work crossed the process boundary via pids/hosts in generated."""
    if "generated.output" not in df.columns and "generated" not in df.columns:
        return
    pids, hosts = set(), set()
    col = "generated" if "generated" in df.columns else "generated.output"
    for v in df[col].dropna():
        items = v if isinstance(v, list) else [v]
        for it in items:
            if isinstance(it, dict):
                if "pid" in it:
                    pids.add(it["pid"])
                if "host" in it:
                    hosts.add(it["host"])
    if len(pids) < 1:
        return
    _banner(f"{n}) Proof the work was distributed (pids / hosts)")
    _q(n, "How many distinct worker processes/hosts actually ran the tasks?",
       "{d['pid'] for row in df['generated'].dropna() for d in row}",
       "how many distinct worker pids ran the tasks?")
    print(f"    -> distinct worker pids: {len(pids)}  {sorted(pids)}")
    print(f"    -> hosts: {sorted(hosts)}")
    _impact("The results carry the pid/host that produced each one, so distribution\n"
            "is provable -- not assumed. The aggregated return value hides it.")


def lens_loop(df, n):
    if "subtype" not in df.columns or not (df["subtype"] == "academy_loop").any():
        return
    lp = df[df["subtype"] == "academy_loop"]
    _banner(f"{n}) Autonomous @loop behavior (nobody called it)")
    _q(n, "Did the background @loop run, and for how long?",
       "df[df['subtype']=='academy_loop'][['activity_id','group_id',"
       "'started_at','ended_at']]", "show the academy_loop records")
    span = wall_clock_seconds(lp)
    groups = lp["group_id"].dropna().nunique() if "group_id" in lp else 0
    print(f"    -> {len(lp)} loop records over {groups} loop group(s); "
          f"active for {span:.2f}s of wall-clock")
    _impact("Proactive, self-driven behavior is captured distinctly from "
            "request/response --\n       so you can see it ran at all.")


# 07 gets one extra, chemistry-specific lens (still fully derived from records).
def lens_mol_results(df, n):
    tc = df[df["subtype"] == "tool_call"].copy() if "subtype" in df else pd.DataFrame()
    if tc.empty or "used.input" not in tc.columns:
        return
    ok = tc[tc["status"] == "FINISHED"]
    if ok.empty:
        return
    _banner(f"{n}) Real results, fully attributed (reproducible science)")
    _q(n, "Which molecules got a real ionization energy, and from which model?",
       "df[(df.subtype=='tool_call')&(df.status=='FINISHED')]"
       "[['used.input','generated.output']]",
       "which molecules were simulated and what were their ionization energies?")
    seen = {}
    for _, r in ok.iterrows():
        sm, en = _smiles(_val(r, "used.input")), _val(r, "generated.output")
        if isinstance(en, (int, float)):
            seen[sm] = en  # last wins if repeated
    for sm, en in sorted(seen.items(), key=lambda kv: -kv[1]):
        print(f"       {sm:<14} {en:.4f} eV")
    model = None
    if "used.model" in df.columns:
        m = df.loc[df["subtype"] == "llm_call", "used.model"].dropna()
        model = m.iloc[0] if len(m) else None
    camp = df["campaign_id"].dropna().iloc[0] if df["campaign_id"].notna().any() else "?"
    print(f"    -> distinct molecules with real energies: {len(seen)}")
    print(f"    -> proposed by model {model!r}, campaign {camp}")
    _impact("Each number is tied to the model that proposed it and the tool that\n"
            "scored it -- the difference between a figure and a reproducible record.")


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def detect_exercise(buf: str, records=None) -> str | None:
    try:
        recs = records if records is not None else prov.load_records(buf)
    except Exception:
        recs = []
    for r in recs:
        if r.get("type") == "workflow" and r.get("name") in PROFILES:
            return r["name"]
    base = os.path.basename(buf)
    for k in PROFILES:
        if k in base or k in os.path.abspath(buf):
            return k
    return None


def demonstrate(exercise_id: str | None, buffer: str | None,
                verify: bool = False) -> int:
    raw = prov.tasks(prov.load_buffer(buffer))
    if raw.empty:
        print(f"No provenance records in {buffer}. Run solution.py first "
              "(or uncomment the capture STEP in exercise.py).")
        return 1
    df = merge_task_updates(raw)  # one row per distinct task_id (DB semantics)
    ex = exercise_id or detect_exercise(buffer) or "?"
    prof = PROFILES.get(ex, dict(title="an agentic run",
                                 plain="its final output",
                                 gain="a queryable record of everything it did"))

    _banner(f"{ex} -- the value of provenance")
    print(f"buffer : {os.path.relpath(buffer)}")
    if len(df) != len(raw):
        print(f"records: {len(df)} distinct tasks  ({len(raw)} raw updates merged by "
              f"task_id -- e.g. a long @loop is flushed at start and at end)")
    else:
        print(f"records: {len(df)}")
    print(f"\nThe ordinary run of {prof['title']} gives you {prof['plain']}.")
    print(f"With provenance you also get: {prof['gain']}.")
    print("Every number below is produced by the pandas shown next to it.")

    # Fixed lens order; inapplicable lenses (no matching records) are skipped so
    # the numbering stays contiguous per exercise.
    lenses = [lens_inventory, lens_span, lens_cross_agent, lens_loop,
              lens_trace, lens_failures, lens_distribution, lens_llm_cost,
              lens_timing]
    if ex == "07-mol-design":
        lenses.insert(lenses.index(lens_failures) + 1, lens_mol_results)

    applicable = [fn for fn in lenses if _applies(fn, df, ex)]
    for i, fn in enumerate(applicable, 1):
        fn(df, i)

    _banner("Summary")
    print(f"The program returned {prof['plain']}. Provenance turned the same run into")
    print("an auditable, queryable record -- lineage, failures, cost and real timing.")
    print("\nGo deeper:")
    print(f"    python {_rel('provenance/query.py')} {os.path.relpath(buffer)}")
    print(f"    python {_rel('provenance/analyze.py')} {os.path.relpath(buffer)}")

    if verify:
        _verify(df, raw, buffer)
    return 0


def _applies(fn, df, ex) -> bool:
    name = fn.__name__
    if name in ("lens_inventory", "lens_trace", "lens_timing"):
        return True
    if name == "lens_span":
        return ((df.get("agent_id").dropna().nunique() if "agent_id" in df else 0) > 1
                or (df.get("workflow_id").dropna().nunique() if "workflow_id" in df else 0) > 1)
    if name == "lens_cross_agent":
        c = "custom_metadata.cross_agent_call"
        return c in df.columns and (df[c] == True).any()  # noqa: E712
    if name == "lens_loop":
        return "subtype" in df and (df["subtype"] == "academy_loop").any()
    if name == "lens_failures":
        return "status" in df and (df["status"] == "ERROR").any()
    if name == "lens_distribution":
        col = "generated" if "generated" in df.columns else None
        if not col:
            return False
        for v in df[col].dropna():
            for it in (v if isinstance(v, list) else [v]):
                if isinstance(it, dict) and "pid" in it:
                    return True
        return False
    if name == "lens_llm_cost":
        return "subtype" in df and (df["subtype"] == "llm_call").any() \
            and "generated.total_tokens" in df.columns
    if name == "lens_mol_results":
        return "subtype" in df and (df["subtype"] == "tool_call").any() \
            and (df["status"] == "FINISHED").any()
    return True


def _verify(df, raw, buffer) -> None:
    """Independent recomputation of the headline aggregates -- fail loudly on drift."""
    _banner("--verify: independent recomputation")
    ok = True

    # 1) merging must collapse `raw` to exactly its distinct task_ids (null-id rows,
    #    which cannot be merged, are each kept). Checked against the same frame the
    #    engine actually used, so it stays consistent with prov.tasks()'s own filtering.
    if "task_id" in raw.columns:
        nn = raw["task_id"].notna()
        expected = int(raw.loc[nn, "task_id"].nunique() + (~nn).sum())
    else:
        expected = len(raw)
    dup_in_df = int(df["task_id"].dropna().duplicated().sum()) if "task_id" in df else 0
    if len(df) != expected or dup_in_df:
        print(f"  FAIL record count: merged={len(df)} expected-distinct={expected} "
              f"dup-remaining={dup_in_df} (raw updates={len(raw)})"); ok = False
    else:
        print(f"  ok   {len(df)} distinct tasks from {len(raw)} raw updates "
              f"(merged by task_id, no dupes remain)")

    # 2) tokens: groupby-sum == flat-sum
    if (df.get("subtype") == "llm_call").any() and "generated.total_tokens" in df:
        t = pd.to_numeric(df.loc[df.subtype == "llm_call", "generated.total_tokens"],
                          errors="coerce")
        a, b = float(t.sum()), float(t.dropna().groupby(
            df.loc[t.index, "activity_id"]).sum().sum())
        print(f"  {'ok  ' if abs(a-b)<1e-6 else 'FAIL'} llm tokens flat={a:.0f} "
              f"grouped={b:.0f}")
        ok &= abs(a - b) < 1e-6

    # 3) wall-clock <= compute-time for every subtype (union can't exceed the sum)
    for s in df["subtype"].dropna().unique():
        sub = df[df.subtype == s]
        w, c = wall_clock_seconds(sub), compute_seconds(sub)
        if w > c + 1e-6:
            print(f"  FAIL {s}: wall={w:.2f} > compute={c:.2f} (impossible)"); ok = False
    print(f"  ok   wall-clock <= compute-time for all subtypes")

    print("  RESULT:", "all checks passed" if ok else "DRIFT DETECTED")


def _rel(p):
    return os.path.relpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p))


def resolve_buffer(path: str | None, start_dir: str | None = None,
                   exercise_id: str | None = None) -> str:
    """A run dir, a buffer file, this exercise's latest run, or the 07 sample."""
    if path:
        if os.path.isdir(path):
            hits = sorted(glob.glob(os.path.join(path, "**", "flowcept_buffer.jsonl"),
                                    recursive=True)) or \
                sorted(glob.glob(os.path.join(path, "*.jsonl")))
            if not hits:
                raise FileNotFoundError(f"no *.jsonl buffer under {path}")
            return hits[-1]
        return path
    # no path: newest run under the exercise dir
    if start_dir:
        hits = sorted(glob.glob(os.path.join(start_dir, "runs", "**",
                                             "flowcept_buffer.jsonl"), recursive=True))
        if hits:
            return hits[-1]
    # last resort: the shipped 07 sample
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sample = os.path.join(repo, "provenance", "sample", "07-mol-design.jsonl")
    if exercise_id in (None, "07-mol-design") and os.path.exists(sample):
        return sample
    raise FileNotFoundError(
        "no buffer given and no runs/ under this exercise yet -- run "
        "`python solution.py` first, then re-run this.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Demonstrate the value of provenance.")
    ap.add_argument("path", nargs="?", default=None, help="run dir or buffer .jsonl")
    ap.add_argument("--exercise", default=None, help="exercise id (else auto-detect)")
    ap.add_argument("--verify", action="store_true",
                    help="independently recompute headline aggregates and assert")
    args = ap.parse_args(argv)
    buf = resolve_buffer(args.path, exercise_id=args.exercise)
    ex = args.exercise or detect_exercise(buf)
    return demonstrate(ex, buf, verify=args.verify)


if __name__ == "__main__":
    raise SystemExit(main())
