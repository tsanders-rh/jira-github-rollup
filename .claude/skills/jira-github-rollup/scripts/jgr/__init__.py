"""Deterministic half of the jira-github-rollup skill.

Collection, caching, change detection, counting, rendering and snapshotting
live here. Reading a requirement and deciding what a piece of evidence proves
stays with the model; nothing in this package makes that judgement.

Stdlib only, Python 3.9+. No network access except through `gh`, which is
read-only by construction (see `ghclient`).
"""

__all__ = [
    "assemble",
    "cache",
    "collect",
    "convert",
    "diff",
    "evidence",
    "ghclient",
    "measure",
    "metrics",
    "refs",
    "render",
    "snapshots",
    "util",
]
