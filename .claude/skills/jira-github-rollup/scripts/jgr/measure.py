"""Measure how much text a run puts in front of the model.

Only what the model actually reads counts: the manifests, diffs, excerpts and
reference files handed to it, not the cached raw responses sitting on disk.

Tokens are reported only when a tokenizer is installed. Otherwise the numbers
are bytes and characters and are labelled as such - an estimate divided by
four is not a measurement, and a saving nobody counted is not a saving.
"""

from __future__ import annotations

import os


def _tokenizer():
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding("cl100k_base"), "tiktoken/cl100k_base"
    except Exception:
        return None, None


def measure_text(text, label=None):
    encoder, name = _tokenizer()
    result = {
        "label": label,
        "bytes": len(text.encode("utf-8")),
        "chars": len(text),
        "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "tokens": None,
        "tokenizer": name,
        "unit": "bytes and characters (no tokenizer installed)",
    }
    if encoder is not None:
        result["tokens"] = len(encoder.encode(text))
        result["unit"] = f"tokens ({name})"
    return result


def measure_paths(paths, label=None):
    items, missing = [], []
    for path in paths:
        if not os.path.isfile(path):
            missing.append(path)
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            items.append(measure_text(handle.read(), label=path))
    total = {
        "label": label,
        "bytes": sum(item["bytes"] for item in items),
        "chars": sum(item["chars"] for item in items),
        "lines": sum(item["lines"] for item in items),
        "tokens": sum(item["tokens"] for item in items) if items and items[0]["tokens"] is not None else None,
        "tokenizer": items[0]["tokenizer"] if items else None,
        "unit": items[0]["unit"] if items else "no files measured",
    }
    return {"total": total, "items": items, "missing": missing}
