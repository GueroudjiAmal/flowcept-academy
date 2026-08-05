#!/usr/bin/env python
"""07-mol-design -- the value of provenance (thin wrapper over provenance/value.py).

Answers questions the campaign's normal output cannot -- cross-framework lineage,
the LLM's invalid SMILES and its recovery, per-molecule xTB results tied to the
model, and RIGOROUS cost/timing (wall-clock is the union of overlapping intervals,
never a sum of parallel tasks). Every number is paired with the pandas that yields it.

    python provenance_value.py                 # newest runs/ buffer, else the sample
    python provenance_value.py runs/07-mol-design_*
    python provenance_value.py --verify        # independently recompute + assert

The engine (and the full list of "lenses") lives in provenance/value.py.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_REPO, "provenance"))

import value  # noqa: E402

EXERCISE = "07-mol-design"

if __name__ == "__main__":
    argv = sys.argv[1:]
    verify = "--verify" in argv
    positional = [a for a in argv if not a.startswith("-")]
    buf = value.resolve_buffer(positional[0] if positional else None,
                               start_dir=_HERE, exercise_id=EXERCISE)
    raise SystemExit(value.demonstrate(EXERCISE, buf, verify=verify))
