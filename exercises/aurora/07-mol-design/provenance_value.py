#!/usr/bin/env python
"""
07-mol-design -- WHY provenance matters (a runnable demonstration)
==================================================================

Exercise 07 runs a *real* agentic chemistry campaign: an Academy `@loop` drives a
LangGraph reasoning graph (plan -> tool_calling -> simulate -> conclude -> critique
-> update) whose `simulate` step evaluates each LLM-proposed molecule with an
**actual GFN2-xTB** ionization-energy calculation (rdkit + ASE + xtb). Three
frameworks, one process, and -- with Flowcept -- ONE provenance graph.

This file is NOT another way to run the campaign. It takes a buffer that a run
already produced and asks a series of questions that are **impossible to answer
from the program's normal output** -- then shows the answer provenance gives you.
Each block prints:

    Q:   the question (in plain English -- the same phrasing works with
         `query.py --ask "..."`)
    >>>  the exact pandas over the provenance DataFrame `df`
    ->   the answer, computed from the captured records
    !!   what you would have been blind to WITHOUT provenance

Everything here is plain pandas (no LLM needed), so it runs anywhere the buffer
does. Point it at a run you produced, or let it default to the shipped sample:

    python provenance_value.py                                   # shipped sample
    python provenance_value.py runs/07-mol-design_*              # your own run
    python provenance_value.py runs/07-mol-design_*/flowcept_buffer.jsonl

Companion to `query.py` (natural-language -> pandas) and `analyze.py` (full report).
"""
from __future__ import annotations

import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

import pandas as pd  # noqa: E402

from flowcept_academy import provenance as prov  # noqa: E402


# --------------------------------------------------------------------------- #
# buffer resolution -- a run dir, a buffer file, or the shipped sample
# --------------------------------------------------------------------------- #
def _resolve_buffer(path: str | None) -> str:
    repo = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    sample = os.path.join(repo, "provenance", "sample", "07-mol-design.jsonl")
    if not path:
        return sample
    if os.path.isdir(path):
        hits = sorted(glob.glob(os.path.join(path, "**", "flowcept_buffer.jsonl"),
                                recursive=True))
        hits += sorted(glob.glob(os.path.join(path, "*.jsonl")))
        if not hits:
            raise FileNotFoundError(f"no *.jsonl provenance buffer under {path}")
        return hits[0]
    return path


# --------------------------------------------------------------------------- #
# tiny presentation helpers
# --------------------------------------------------------------------------- #
_W = 78


def hr(ch: str = "-") -> None:
    print(ch * _W)


def banner(title: str) -> None:
    print("\n" + "=" * _W)
    print(title)
    print("=" * _W)


def q(n: int, question: str, code: str, nl: str) -> None:
    print(f"\nQ{n}. {question}")
    print(f"    >>> {code}")
    print(f'    (natural language:  query.py --ask "{nl}")')


def impact(line: str) -> None:
    print(f"    !! Without provenance: {line}")


def _smiles(used_input) -> str:
    """tool_call `used.input` is like \"{'smiles': 'CNC(N)=O'}\" -- pull the SMILES."""
    if not isinstance(used_input, str):
        return "?"
    m = re.search(r"'smiles':\s*'([^']*)'", used_input)
    return m.group(1) if m else used_input


# --------------------------------------------------------------------------- #
def main() -> int:
    buf = _resolve_buffer(sys.argv[1] if len(sys.argv) > 1 else None)
    df = prov.tasks(prov.load_buffer(buf))
    if df.empty:
        print(f"No provenance records in {buf}")
        return 1

    banner("07-mol-design -- the value of provenance, in questions you "
           "otherwise can't answer")
    print(f"buffer: {os.path.relpath(buf)}")
    print(f"tasks : {len(df)} provenance records")
    print("\nThe campaign's normal output is a ranked list of molecules. Everything")
    print("below -- the failures, the recovery, the cost, the cross-framework lineage")
    print("-- is INVISIBLE in that output. Provenance is the difference.")

    # ---- Q1: one graph across three frameworks -------------------------- #
    banner("1) Cross-framework lineage: three frameworks, ONE graph")
    q(1, "How much of each kind of work happened, across all frameworks?",
      "df['subtype'].value_counts()",
      "how many tasks of each subtype?")
    counts = df["subtype"].value_counts()
    print("    ->")
    for k, v in counts.items():
        layer = {
            "academy_lifecycle": "Academy   (agent lifecycle)",
            "academy_loop": "Academy   (@loop campaign)",
            "academy_action": "Academy   (action, e.g. report)",
            "langgraph_node": "LangGraph (reasoning node)",
            "llm_call": "LangChain (llm.ainvoke)",
            "tool_call": "LangChain (xTB tool call)",
        }.get(k, "")
        print(f"       {k:<20} {v:>3}   {layer}")
    ncamp = df["campaign_id"].nunique() if "campaign_id" in df else 0
    print(f"    -> distinct campaign_id values tying it together: {ncamp}")
    impact("Academy, LangGraph and the LLM/tool calls live in three separate "
           "libraries;\n       their logs would be three disconnected streams. "
           "Here they are one\n       graph under a single campaign_id -- with "
           "zero edits to the agent code.")

    # ---- Q2: the hidden failure rate ------------------------------------ #
    banner("2) The hidden failure rate: what the LLM got WRONG")
    q(2, "Which molecule evaluations failed, and why?",
      "df[(df.subtype=='tool_call') & (df.status=='ERROR')][['used.input','stderr']]",
      "which tasks have status ERROR and what is the stderr?")
    tc = df[df.subtype == "tool_call"].copy()
    errs = tc[tc.status == "ERROR"]
    oks = tc[tc.status == "FINISHED"]
    print(f"    -> {len(errs)} of {len(tc)} tool calls FAILED "
          f"({(len(errs)/max(len(tc),1))*100:.0f}%). The LLM invented SMILES that "
          f"RDKit rejects:")
    for _, r in errs.iterrows():
        print(f"       x {_smiles(r.get('used.input')):<14} "
              f"{str(r.get('stderr') or '').strip()}")
    impact("The final ranked list shows only the molecules that WORKED. You would\n"
           "       never know the agent spent most of its tool calls on invalid\n"
           "       chemistry -- nor which strings to blame when results look thin.")

    # ---- Q3: black-box output vs. what really happened ------------------ #
    banner("3) What the black box hid: visible output vs. reality")
    reps = df[df.activity_id == "report"]
    visible = 0
    for c in ("generated.output", "generated.outputs"):
        if c in reps.columns:
            for v in reps[c].dropna():
                if isinstance(v, (list, tuple)):
                    visible = max(visible, len(v))
    q(3, "How many molecules did the campaign actually evaluate, "
         "vs. how many the run printed?",
      "df[df.subtype=='tool_call'].shape[0]   # attempted",
      "how many molecules were simulated in total?")
    print(f"    -> molecules the run's report surfaced : {visible}")
    print(f"    -> molecules actually attempted        : {len(tc)}")
    print(f"    -> real xTB energies computed          : {len(oks)}")
    impact("A short/empty report reads like 'nothing happened'. Provenance proves\n"
           "       the campaign attempted %d molecules and produced %d real "
           "energies --\n       the work is recorded even when the summary "
           "doesn't show it." % (len(tc), len(oks)))

    # ---- Q4: the reasoning trace / self-recovery ------------------------ #
    banner("4) The reasoning trace: watch the agent recover from its mistakes")
    q(4, "In what order were molecules proposed, and did each parse?",
      "df[df.subtype=='tool_call'].sort_values('started_at')"
      "[['used.input','status']]",
      "list the tool calls in time order with their status")
    seq = tc.sort_values("started_at") if "started_at" in tc.columns else tc
    print("    -> (in the order the agent tried them)")
    for i, (_, r) in enumerate(seq.iterrows(), 1):
        mark = "ok " if r.get("status") == "FINISHED" else "FAIL"
        eng = r.get("generated.output")
        tail = f"-> {eng:.3f} eV" if (pd.notna(eng) and isinstance(eng, (int, float))) else ""
        print(f"       {i:>2}. [{mark}] {_smiles(r.get('used.input')):<14} {tail}")
    impact("This is the agent THINKING: propose -> fail -> the graph's "
           "conclude/critique/\n       update nodes feed the failure back -> the "
           "model fixes the SMILES and\n       succeeds. Without provenance the "
           "loop is an opaque black box.")

    # ---- Q5: real, fully-attributed scientific results ------------------ #
    banner("5) Real results, fully attributed (reproducible science)")
    q(5, "Which molecules were simulated and what were their ionization energies?",
      "df[(df.subtype=='tool_call') & (df.status=='FINISHED')]"
      "[['used.input','generated.output']]",
      "which molecules were simulated and what were their ionization energies?")
    print("    -> real GFN2-xTB ionization energies:")
    for _, r in oks.sort_values("generated.output", ascending=False).iterrows() \
            if "generated.output" in oks.columns else oks.iterrows():
        eng = r.get("generated.output")
        eng = f"{eng:.4f} eV" if isinstance(eng, (int, float)) else str(eng)
        print(f"       {_smiles(r.get('used.input')):<14} {eng}")
    model = None
    if "used.model" in df.columns:
        m = df.loc[df.subtype == "llm_call", "used.model"].dropna()
        model = m.iloc[0] if len(m) else None
    model = model or (df.loc[df.subtype == "llm_call", "activity_id"].dropna().iloc[0]
                      if (df.subtype == "llm_call").any() else "?")
    print(f"    -> every number above is tied to campaign_id {ncamp and df['campaign_id'].dropna().iloc[0]}")
    print(f"       proposed by model: {model}")
    impact("A paper reports '14.12 eV'. Provenance tells you WHICH model proposed\n"
           "       the molecule, in WHICH campaign, scored by WHICH tool -- the "
           "difference\n       between a number and a reproducible scientific record.")

    # ---- Q6: cost & compute accounting ---------------------------------- #
    banner("6) Cost & compute accounting: where did the time and tokens go?")
    q(6, "How many LLM tokens did the campaign spend, and where did wall-clock go?",
      "df[df.subtype=='llm_call']['generated.total_tokens'].sum()",
      "how many tokens did the llm_call rows use in total?")
    llm = df[df.subtype == "llm_call"]
    tok = pd.to_numeric(llm.get("generated.total_tokens"), errors="coerce").sum() \
        if "generated.total_tokens" in llm.columns else 0
    print(f"    -> LLM: {len(llm)} calls, {int(tok):,} total tokens "
          f"for {len(oks)} valid molecule(s) "
          f"({int(tok)//max(len(oks),1):,} tokens per usable result)")
    if {"started_at", "ended_at"}.issubset(tc.columns):
        tc["_el"] = (tc["ended_at"] - tc["started_at"]).astype(float)
        ok_t = tc.loc[tc.status == "FINISHED", "_el"].sum()
        err_t = tc.loc[tc.status == "ERROR", "_el"].sum()
        print(f"    -> xTB wall-clock: {ok_t:6.1f}s on {len(oks)} REAL relaxations, "
              f"{err_t:5.1f}s wasted on {len(errs)} invalid SMILES")
    impact("LLM spend and simulation time are attributed per call, so you can cost\n"
           "       a campaign, spot the 4-minute relaxations, and see how cheap the\n"
           "       failed parses were -- none of which the program's output reveals.")

    # ---- close ---------------------------------------------------------- #
    banner("Summary")
    print("The campaign's output was a list of molecules. Provenance turned that")
    print("into an auditable record: a cross-framework lineage graph, the LLM's")
    print("wrong turns and its recovery, per-molecule xTB results tied to the model")
    print("that proposed them, and full token/time accounting. That is the impact --")
    print("the same run, made explainable, debuggable, reproducible and costable.")
    print("\nExplore further:")
    print(f"    python ../../../provenance/query.py {os.path.relpath(buf)}")
    print(f"    python ../../../provenance/analyze.py {os.path.relpath(buf)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
