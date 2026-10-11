"""Shared helpers: time, hashing, canonical JSON, rounding, text normalization.

Every rule encoded here is one the skill used to state in prose and an agent had
to apply by hand. Rounding and text normalization in particular were the two
most likely to drift between runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timezone

ISO = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO)


def stamp(dt: datetime) -> str:
    """Filename timestamp: 20261102T090412Z. Sorts lexically."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_iso(value):
    """Parse an ISO 8601 instant. Returns None for anything unusable.

    None matters: an evidence item with no usable timestamp is `undetermined`,
    never defaulted to progress.
    """
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def date_only(value) -> str:
    dt = parse_iso(value)
    return dt.strftime("%Y-%m-%d") if dt else "unknown date"


def days_between(later, earlier):
    a, b = parse_iso(later), parse_iso(earlier)
    if not a or not b:
        return None
    return (a - b).days


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(obj) -> str:
    text = obj if isinstance(obj, str) else canonical(obj)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def round_half_up(value: float) -> int:
    """Round half away from zero.

    Python's round() is banker's rounding: round(0.5) == 0. A percentage that
    flips depending on parity is the kind of difference a reader reads as
    movement.
    """
    return int(math.floor(value + 0.5)) if value >= 0 else -int(math.floor(-value + 0.5))


def normalize_text(text: str) -> str:
    """Normalize a requirement for *matching only*.

    The verbatim text is what the snapshot stores and what the report prints.
    This is the comparison key: NFC, trimmed, internal whitespace collapsed.
    """
    if text is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, normalize_text(a).lower(), normalize_text(b).lower()).ratio()


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, data) -> None:
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def emit(data, path=None) -> None:
    """Write JSON to a file, or to stdout when no path is given."""
    if path:
        write_json(path, data)
        print(path)
    else:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")


def pluralize(count: int, singular: str, plural=None) -> str:
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count} {word}"


def window(text, pattern=None, context=2, max_chars=4000):
    """A bounded, line-oriented read of one body. Truncation is always reported.

    Shared by `excerpt` and `source` so a follow-up read of a file and a read
    of a PR description behave identically: same regex semantics, same context
    lines, same ceiling, same `truncated` flag. A reader who cannot tell which
    command produced a payload should not have to.
    """
    matched = None
    if pattern:
        compiled = re.compile(pattern, re.I)
        lines = text.splitlines()
        keep = set()
        for index, line in enumerate(lines):
            if compiled.search(line):
                keep.update(range(max(0, index - context), min(len(lines), index + context + 1)))
        matched = sum(1 for line in lines if compiled.search(line))
        text = "\n".join(lines[index] for index in sorted(keep))
    return {
        "matchedLines": matched,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "fullChars": len(text),
    }
