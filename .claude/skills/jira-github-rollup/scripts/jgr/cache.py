"""Local evidence cache.

Raw `gh` responses go here and stay here. The manifest the LLM reads carries
identifiers, states, timestamps, hashes, and the path to the raw file - never
the raw file's contents. Anything the LLM actually needs to read is fetched
deliberately with `rollup.py excerpt`.
"""

from __future__ import annotations

import os
import re

from . import util

DEFAULT_HOME = "~/.jira-github-rollup"


def home() -> str:
    return os.path.expanduser(os.environ.get("JGR_HOME", DEFAULT_HOME))


def snapshot_dir(jira_key: str) -> str:
    return os.path.join(home(), "snapshots", jira_key)


def cache_dir(jira_key: str) -> str:
    return os.path.join(home(), "cache", jira_key)


def slug(ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", ref).strip("-").lower()


class Cache:
    """Content-addressed-ish store for raw API responses.

    Files are named for the artifact, not the content, so a re-run overwrites
    the *cache* (which is a cache) while the snapshot store stays append-only
    (which is a record). The two are deliberately different.
    """

    def __init__(self, jira_key: str, root=None, reuse=False):
        self.root = root or cache_dir(jira_key)
        self.jira_key = jira_key
        # Off by default, and that is the important part: change detection
        # depends on this run actually asking GitHub. The cache exists to keep
        # raw payloads out of context and to serve `excerpt`, not to save
        # calls. `reuse=True` is for re-rendering a run offline.
        self.reuse = reuse

    def path_for(self, kind: str, ref: str) -> str:
        return os.path.join(self.root, kind, f"{slug(ref)}.json")

    def rel_for(self, kind: str, ref: str) -> str:
        """The path as the manifest records it, relative to `cacheDir`.

        The manifest names the root once. Repeating an absolute path on every
        child and every pull request is several kilobytes of identical prefix
        in something whose whole job is to be small.
        """
        return os.path.join(kind, f"{slug(ref)}.json")

    def put(self, kind: str, ref: str, data) -> dict:
        path = self.path_for(kind, ref)
        util.write_json(path, data)
        return {"path": path, "hash": util.sha256(data)}

    def get(self, kind: str, ref: str):
        """Read a cached response. Returns None unless reuse is enabled."""
        if not self.reuse:
            return None
        return self.read(kind, ref)

    def read(self, kind: str, ref: str):
        """Read a cached response regardless of the reuse setting."""
        path = self.path_for(kind, ref)
        if not os.path.exists(path):
            return None
        try:
            return util.read_json(path)
        except (ValueError, OSError):
            return None

    def has(self, kind: str, ref: str) -> bool:
        return os.path.exists(self.path_for(kind, ref))
