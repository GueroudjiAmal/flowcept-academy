"""Flowcept x Academy -- 1-hour tutorial package (provenance-focused).

A compact toolkit for capturing and analyzing the provenance of Academy
multi-agent workflows with Flowcept:

* :mod:`flowcept_academy.capture`     -- ``captured()``: thin wrapper over the
  Flowcept agentic-branch plugins (``FlowceptAcademyPlugin`` /
  ``FlowceptLangGraphPlugin``) -- turn provenance on/off
* :mod:`flowcept_academy.provenance`  -- load / query / analyze provenance (terminal-only)
* :mod:`flowcept_academy.util`        -- ``run()`` / ``capture_run()`` helpers

This is a small, reusable library. The hands-on material lives in the top-level
``exercises/`` tree (``local/`` and ``aurora/``), where each stock Academy
example is a self-contained, step-by-step provenance exercise built on top of
these modules. Analysis is entirely terminal-based (no images) so it works over
SSH on Aurora.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["capture", "provenance", "util"]
