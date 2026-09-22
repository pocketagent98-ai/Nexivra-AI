"""Untrusted-content handling (prompt-injection defense).

Web pages, PDFs, repositories, search results and uploaded documents are
UNTRUSTED DATA. They can be evidence; they are never authority over system
policy. ``defuse`` wraps retrieved content in explicit data fences and
neutralises the most common instruction-shaped patterns before the text
is ever placed inside a prompt.
"""

from __future__ import annotations

import re

FENCE_OPEN = "<untrusted-content>"
FENCE_CLOSE = "</untrusted-content>"

INJECTION_PATTERNS = [
    (re.compile(r"(?i)ignore (all|any|previous|prior|above) (previous |prior |above )?(instructions?|prompts?|rules?)"), "[neutralized-injection]"),
    (re.compile(r"(?i)disregard (all|any|the) (previous|prior|above) (instructions?|context|rules?)"), "[neutralized-injection]"),
    (re.compile(r"(?i)you are now (a|an|the) [^.]{0,80}"), "[neutralized-injection]"),
    (re.compile(r"(?i)\b(system|developer|assistant)\s*:"), "[neutralized-role]"),
    (re.compile(r"(?i)new instructions?\s*:"), "[neutralized-injection]"),
    (re.compile(r"(?i)reveal (your|the) (system )?prompt"), "[neutralized-injection]"),
    (re.compile(r"(?i)(api[_ ]?key|secret|password)\s*(is|:)\s*\S+"), "[neutralized-credential]"),
]

MAX_CONTENT_CHARS = 200_000


def contains_injection(text: str) -> bool:
    return any(p.search(text) for p, _ in INJECTION_PATTERNS)


def defuse(text: str, *, max_chars: int = MAX_CONTENT_CHARS) -> str:
    """Neutralise instruction-shaped text and fence it as pure data.

    The fenced output is what any prompt-building code must use; the model
    is always told that anything inside the fence is evidence, not orders.
    """
    if not text:
        return f"{FENCE_OPEN}\n{FENCE_CLOSE}"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...truncated...]"
    for pattern, repl in INJECTION_PATTERNS:
        text = pattern.sub(repl, text)
    body = text.replace(FENCE_OPEN, "[literal-fence]").replace(FENCE_CLOSE, "[literal-fence]")
    return f"{FENCE_OPEN}\n{body}\n{FENCE_CLOSE}"
