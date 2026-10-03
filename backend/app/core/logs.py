"""Structured logging (Phase 12B D44).

Every logger writes one JSON object per line: `ts` (UTC, ISO 8601), `level`, `logger`, `message`, `request_id` (the request / job
correlation id from the context), plus structured fields passed as `extra={"fields": {...}}` (route, method, status, duration_ms,
user_id, job_id, job_code, environment, …). `LOG_FORMAT=text` gives a readable line for local development; production refuses it.

Never logged (defence in depth — callers must not pass them in the first place):
- any field whose name looks like a secret or personal data (password, token, secret, authorization, cookie, api key, account
  number, IFSC / routing code, KYC / ID number, phone, email) is replaced by "[REDACTED]";
- bearer tokens, JWTs, Fernet tokens and `password=` style pairs are masked inside message text.
Request bodies, query strings, headers and file contents are never logged.
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.context import current_request_id

_SENSITIVE_KEY = re.compile(r"pass(word|wd)?|secret|token|authori[sz]ation|cookie|api[_-]?key|account(_number)?|ifsc|routing|kyc|"
                            r"id_number|aadhaar|pan_number|phone|mobile|email|bank", re.I)
_SENSITIVE_TEXT = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[REDACTED-JWT]"),
    (re.compile(r"gAAAAA[A-Za-z0-9_=-]{20,}"), "[REDACTED-FERNET]"),
    (re.compile(r"(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;&]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(rediss?://[^:/@\s]*:)[^@\s]+@"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)(mssql\+pyodbc://[^:/@\s]*:)[^@\s]+@"), r"\1[REDACTED]@"),
]


def scrub_text(text: str) -> str:
    for pattern, repl in _SENSITIVE_TEXT:
        text = pattern.sub(repl, text)
    return text


def scrub(value: Any, key: str | None = None) -> Any:
    if key is not None and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return scrub_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return scrub_text(str(value))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub_text(record.getMessage()),
        }
        rid = current_request_id()
        if rid:
            out["request_id"] = rid
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for k, v in scrub(fields).items():
                out.setdefault(k, v)
        if record.exc_info:
            out["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            out["traceback"] = scrub_text(self.formatException(record.exc_info))
        return json.dumps(out, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = scrub_text(super().format(record))
        fields = getattr(record, "fields", None)
        return f"{line} {json.dumps(scrub(fields), default=str)}" if isinstance(fields, dict) and fields else line


def configure_logging(log_format: str = "json", level: str = "INFO") -> None:
    """Install one stdout handler on the root logger (idempotent). Uvicorn's loggers propagate to it."""
    root = logging.getLogger()
    handler = next((h for h in root.handlers if getattr(h, "_carbon_platform", False)), None)
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)
        handler._carbon_platform = True  # type: ignore[attr-defined]
        for h in list(root.handlers):
            root.removeHandler(h)
        root.addHandler(handler)
    handler.setFormatter(JsonFormatter() if log_format == "json" else TextFormatter())
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # replaced by the structured app.http request log
    logging.getLogger("httpx").setLevel(logging.WARNING)
