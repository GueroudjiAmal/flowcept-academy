#!/usr/bin/env python
"""05-parsl -- the value of provenance (thin wrapper over provenance/value.py).

Answers questions the normal output of an agent delegating to a Parsl task cannot -- what actually ran, in what
order, what it cost, and (where relevant) what failed or crossed an agent/process
boundary. Every number is paired with the exact pandas that yields it, and timing
is rigorous: wall-clock is the union of overlapping intervals, never a sum.

    python provenance_value.py                 # newest runs/ buffer under this dir
    python provenance_value.py runs/05-parsl_*
    python provenance_value.py --verify        # independently recompute + assert

Run `python solution.py` first so there is a runs/ buffer to read. The engine (and
the full list of "lenses") lives in provenance/value.py.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, os.path.join(_REPO, "provenance"))

import value  # noqa: E402

EXERCISE = "05-parsl"

if __name__ == "__main__":
    argv = sys.argv[1:]
    verify = "--verify" in argv
    positional = [a for a in argv if not a.startswith("-")]
    buf = value.resolve_buffer(positional[0] if positional else None,
                               start_dir=_HERE, exercise_id=EXERCISE)
    raise SystemExit(value.demonstrate(EXERCISE, buf, verify=verify))
