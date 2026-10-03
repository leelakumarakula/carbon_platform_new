"""External notification boundary (Phase 12B D39 / D41 / D42). NOTHING IS SENT.

- In-app notifications are unchanged (`services/notification_service.notify`, written in the business transaction).
- SMTP is the selected FUTURE external channel (D39). External delivery is DEFERRED (D41): NOTIFICATION_EXTERNAL_DELIVERY only accepts
  "disabled", `SmtpChannel.send()` always raises `ExternalDeliveryDisabled`, and no job, queue or code path calls it. No credentials
  are invented: SMTP_* settings are empty unless an operator configures them.
- D42 policy, enforced by `delivery_decision()` — the single gate any future delivery job must pass for every message:
    explicit opt-in recorded (never assumed) · not opted out (opt-out always wins) · a preferred language for the template ·
    outside the recipient's quiet hours (deferred, not dropped) · and external delivery enabled.
  Where the preferences are stored, the consent wording and the templates are business decisions that come with D41's delivery
  work; until then no recipient can have an opt-in, so the gate refuses everyone.
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Protocol

from app.core.config import get_settings


class ExternalDeliveryDisabled(RuntimeError):
    """External notification delivery is deferred (D41); nothing may be sent."""


@dataclass(frozen=True)
class ExternalPreferences:
    channel: str                          # EMAIL (SMTP). SMS / WHATSAPP have no selected provider.
    opted_in_at: datetime | None          # explicit opt-in (UTC); None = never opted in
    opted_out_at: datetime | None         # opt-out (UTC); wins over any opt-in
    language: str | None                  # preferred language code for the template
    quiet_start: time | None = None       # local quiet hours [start, end); may wrap midnight
    quiet_end: time | None = None
    utc_offset_minutes: int = 0           # recipient's local offset (e.g. +330 for IST)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str                           # ALLOWED | NO_PREFERENCES | NOT_OPTED_IN | OPTED_OUT | LANGUAGE_REQUIRED | QUIET_HOURS |
                                          # UNSUPPORTED_CHANNEL | DELIVERY_DEFERRED
    retry_at: datetime | None = None      # QUIET_HOURS: earliest UTC time delivery may be attempted


def _in_quiet_hours(local: time, start: time, end: time) -> bool:
    return start <= local < end if start < end else (local >= start or local < end)


def delivery_decision(prefs: ExternalPreferences | None, now_utc: datetime) -> Decision:
    """D42: every check must pass; the first failing one is reported. Pure function (no I/O)."""
    if prefs is None:
        return Decision(False, "NO_PREFERENCES")
    if prefs.channel != "EMAIL":
        return Decision(False, "UNSUPPORTED_CHANNEL")
    if prefs.opted_out_at is not None and (prefs.opted_in_at is None or prefs.opted_out_at >= prefs.opted_in_at):
        return Decision(False, "OPTED_OUT")
    if prefs.opted_in_at is None:
        return Decision(False, "NOT_OPTED_IN")
    if not (prefs.language or "").strip():
        return Decision(False, "LANGUAGE_REQUIRED")
    if prefs.quiet_start is not None and prefs.quiet_end is not None and prefs.quiet_start != prefs.quiet_end:
        offset = timedelta(minutes=prefs.utc_offset_minutes)
        local = now_utc + offset
        if _in_quiet_hours(local.time(), prefs.quiet_start, prefs.quiet_end):
            end_local = datetime.combine(local.date(), prefs.quiet_end)
            if end_local <= local:
                end_local += timedelta(days=1)
            return Decision(False, "QUIET_HOURS", retry_at=end_local - offset)
    if get_settings().NOTIFICATION_EXTERNAL_DELIVERY != "enabled":
        return Decision(False, "DELIVERY_DEFERRED")
    return Decision(True, "ALLOWED")


class ExternalChannel(Protocol):
    name: str

    def send(self, to: str, subject: str, body: str, language: str) -> str: ...


class SmtpChannel:
    """The future SMTP adapter's boundary (D39). It never opens a connection while delivery is deferred."""
    name = "SMTP"

    def __init__(self) -> None:
        s = get_settings()
        self.host, self.port, self.sender, self.starttls = s.SMTP_HOST, s.SMTP_PORT, s.SMTP_FROM, s.SMTP_STARTTLS

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, to: str, subject: str, body: str, language: str) -> str:
        raise ExternalDeliveryDisabled("External notification delivery is deferred (D41): nothing is sent.")


def deliver_external(channel: ExternalChannel, prefs: ExternalPreferences | None, now_utc: datetime, to: str, subject: str,
                     body: str) -> Decision:
    """The only entry point for external delivery: the D42 gate first, then the channel. Today it always refuses."""
    decision = delivery_decision(prefs, now_utc)
    if not decision.allowed:
        return decision
    assert prefs is not None and prefs.language
    channel.send(to, subject, body, prefs.language)
    return decision
