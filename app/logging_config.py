"""PII-safe logging: redact obvious personal identifiers before anything is written out."""
from __future__ import annotations

import logging
import re

_PATTERNS = [
    (re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}\b"), "[redacted-sin]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[redacted-email]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[redacted-number]"),
]


class PIIRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for pattern, repl in _PATTERNS:
            msg = pattern.sub(repl, msg)
        record.msg = msg
        record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(PIIRedactionFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
