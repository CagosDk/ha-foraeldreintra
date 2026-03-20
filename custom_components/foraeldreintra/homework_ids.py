from __future__ import annotations

import hashlib
import re


def _normalize(value: str | None) -> str:
    """Normalize text so tiny formatting changes matter less."""
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def build_homework_id(
    child_name: str,
    date_text: str,
    subject: str,
    title: str,
    description: str,
    source: str,
) -> str:
    """Build a stable homework ID."""
    raw = "||".join(
        [
            _normalize(child_name),
            _normalize(date_text),
            _normalize(subject),
            _normalize(title),
            _normalize(description),
            _normalize(source),
        ]
    )

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return digest[:16]
