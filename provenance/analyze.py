#!/usr/bin/env python
"""Terminal provenance analysis over a Flowcept buffer (or MongoDB).

Point it at any ``flowcept_buffer.jsonl`` (from a local run, an Aurora run, or the
shipped sample) and it prints -- to the terminal, no images -- a summary + lineage,
a tailored content-aware analysis, per-agent LLM tokens, action timing, capture
overhead, a text dashboard, and writes Flowcept's markdown provenance card.

Examples
--------
    # analyze the shipped sample (example 07: cross-framework + a captured failure)
    python provenance/analyze.py provenance/sample/07-mol-design.jsonl

    # analyze a run you just produced (a run dir or its buffer)
    python provenance/analyze.py runs/06-llm_*/flowcept_buffer.jsonl

    # analyze EVERY buffer under a directory separately
    python provenance/analyze.py --all runs/ --out per_example_out

    # analyze from MongoDB (online profile) by campaign id
    python provenance/analyze.py --from-db --campaign <campaign_id>
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

# Ensure the package is importable when run from a source checkout without install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flowcept_academy import provenance as prov  # noqa: E402


def _report(df, buffer_path: str | None, out_dir: str, stem: str) -> None:
    """Print the full terminal report for one loaded buffer + write its md card."""
    prov.print_summary(df)
    print()
    prov.print_lineage(df)
    if buffer_path is not None:
        prov.print_tailored(prov.load_records(buffer_path))

    print("\n--- LLM calls / tokens by agent ---")
    print(prov.llm_summary(df).to_string(index=False))
    print("\n--- Action timing ---")
    print(prov.action_stats(df).to_string(index=False))

    perf = None
    if buffer_path is not None:
        cand = sorted(glob.glob(os.path.join(os.path.dirname(buffer_path) or ".",
                                             "provenance_perf_*.csv")), key=os.path.getmtime)
        if cand:
            perf = prov.load_perf(cand[-1])
            print("\n--- Provenance capture overhead ---")
            print(prov.perf_summary(perf).to_string(index=False))

    prov.text_dashboard(df, perf=perf, title=f"{stem} -- provenance")

    # Flowcept's built-in provenance card (markdown -- terminal-friendly).
    if buffer_path is not None:
        prov.provenance_card(buffer_path, out_dir=out_dir, stem=stem)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("buffer", nargs="?", default="flowcept_buffer.jsonl",
                    help="a flowcept_buffer.jsonl, a *.jsonl, or a run dir "
                         "(default: ./flowcept_buffer.jsonl)")
    ap.add_argument("--from-db", action="store_true", help="load from MongoDB instead of a buffer")
    ap.add_argument("--campaign", default=None, help="campaign_id filter (with --from-db)")
    ap.add_argument("--out", default=".", help="dir to write provenance card(s) into")
    ap.add_argument("--all", metavar="DIR", default=None,
                    help="analyze EACH *.jsonl buffer under DIR (recursively) separately")
    args = ap.parse_args()

    # Per-example mode: one analysis per buffer found under DIR.
    if args.all:
        buffers = sorted(glob.glob(os.path.join(args.all, "**", "*.jsonl"), recursive=True))
        if not buffers:
            print(f"No *.jsonl buffers found under {args.all}")
            return 1
        os.makedirs(args.out, exist_ok=True)
        for b in buffers:
            name = os.path.splitext(os.path.basename(b))[0]
            print("\n" + "#" * 70)
            print(f"# BUFFER: {b}")
            print("#" * 70)
            df = prov.load_buffer(b)
            if df.empty:
                print("  (no records)")
                continue
            _report(df, b, out_dir=args.out, stem=name)
        print(f"\nDone: {len(buffers)} analyses (markdown cards in {args.out}/).")
        return 0

    if args.from_db:
        print(f"Loading provenance from MongoDB (campaign={args.campaign})...")
        df = prov.load_from_db(campaign_id=args.campaign)
        if df.empty:
            print("No provenance records found.")
            return 1
        print()
        _report(df, None, out_dir=args.out, stem=str(args.campaign or "campaign"))
        return 0

    # A run dir, a buffer file, or the default.
    buffer = args.buffer
    if os.path.isdir(buffer):
        hits = sorted(glob.glob(os.path.join(buffer, "**", "flowcept_buffer.jsonl"),
                                recursive=True)) or sorted(glob.glob(os.path.join(buffer, "*.jsonl")))
        if not hits:
            print(f"No *.jsonl provenance buffer under {buffer}")
            return 1
        buffer = hits[0]

    print(f"Loading provenance buffer: {buffer}")
    df = prov.load_buffer(buffer)
    if df.empty:
        print("No provenance records found.")
        return 1
    print()
    _report(df, buffer, out_dir=args.out,
            stem=os.path.splitext(os.path.basename(buffer))[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
