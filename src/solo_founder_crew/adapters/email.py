"""Email adapter — M2 Phase 2 ``email_tool`` for outbound role messages.

A second real outbound tool alongside ``github_pr.GitHubPRTool``. The
shape mirrors the framework's recurring Protocol-with-fake pattern:

- ``EmailAPI``: a Protocol — the narrow surface ``EmailTool`` needs.
  **Pluggable**: any object implementing ``send_email(...) -> str``
  works. Resend ships as the default; the project registers more
  providers (SMTP, SendGrid, Mailgun, …) via
  ``register_email_provider`` without touching the tool itself.
- ``ResendEmailAPI``: default production implementation,
  lazy-imports ``httpx`` and posts to Resend's REST API. Validates
  ``RESEND_API_KEY`` at construction.
- ``FakeEmailAPI``: in-memory test double. Records every "sent" email
  so tests can assert without touching the network.
- ``EmailTool``: the async callable suitable for
  ``ToolRegistry.register("email_tool", …, escalates=…)``. Takes the
  approved artefact text as input; derives subject from the first
  line; renders both plain-text and HTML bodies; calls the API; returns
  a short status string ("sent:<id>:<recipient>").
- ``make_email_tool``: factory mirroring ``make_github_pr_tool``.
  Reads ``SFC_EMAIL_FROM``, ``SFC_EMAIL_TO``,
  ``SFC_EMAIL_SUBJECT_PREFIX``, and **``SFC_EMAIL_PROVIDER``**
  (default ``"resend"``). The provider name dispatches through the
  module-level provider registry.

Adding a new provider (e.g. SendGrid)::

    from solo_founder_crew.adapters.email import (
        EmailAPI, register_email_provider,
    )

    class SendGridEmailAPI:
        def __init__(self): ...
        def send_email(self, *, from_addr, to, subject, html, text) -> str:
            ...

    register_email_provider("sendgrid", SendGridEmailAPI)

After that, ``SFC_EMAIL_PROVIDER=sendgrid`` (or
``make_email_tool(provider="sendgrid")``) routes through it. The
``EmailTool`` itself does not change; the framework's substitution
seam absorbs the swap.

Design choices worth citing in Ch.3 §3.5/§3.7 prose:

- **Provider-agnostic by design** — the tool depends on an
  ``EmailAPI`` Protocol, not on Resend. Resend is the default because
  it has the cleanest free-tier sandbox for the thesis demo; the
  framework does not couple to it.
- **Resend over SMTP for the default** — modern REST API, no SMTP
  authentication ceremony, free tier (3K/month) covers academic-
  grade demonstration with margin. Sandbox sender
  ``onboarding@resend.dev`` lets the demo work without a verified
  domain (restricted to the account owner's email).
- **Plain-text first** — the approved artefact IS the message body;
  the HTML rendering is a thin paragraph wrapper rather than a
  templated layout. Avoids the trap where the LLM's voice gets
  smothered by branding chrome.
- **One recipient, configured** — the MVP sends to a single
  ``SFC_EMAIL_TO`` address. Multi-recipient / list management /
  inbound-context (reply to a customer who emailed us) all defer to
  M4 (event-driven) when there's a meaningful inbound source.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


# Type alias for a factory that produces an :class:`EmailAPI` with no
# arguments. Providers register one of these in the module-level
# :data:`_PROVIDERS` registry; ``make_email_tool`` dispatches against it.
EmailProviderFactory = Callable[[], "EmailAPI"]


# ─── EmailAPI Protocol + implementations ─────────────────────────────────────


class EmailAPI(Protocol):
    """The narrow surface ``EmailTool`` needs from a mail backend.

    One method. Anything richer (attachments, templates, list
    management) would couple the tool to a specific provider.
    """

    def send_email(
        self,
        *,
        from_addr: str,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> str: ...


@dataclass
class ResendEmailAPI:
    """Production ``EmailAPI`` backed by Resend's REST API.

    Lazy-imports ``httpx`` (already pulled in transitively by
    ``langchain-anthropic``) so the package stays importable on
    systems without HTTP libraries. Validates ``RESEND_API_KEY`` at
    construction.

    For sandbox demonstration use ``onboarding@resend.dev`` as the
    sender — Resend permits it for any new account but restricts
    delivery to the account owner's verified email. For production
    delivery to arbitrary recipients, verify a custom domain in the
    Resend dashboard and use a sender on that domain.
    """

    timeout_seconds: float = 30.0
    _api_key: str = field(init=False)
    _base_url: str = field(default="https://api.resend.com", init=False)

    def __post_init__(self) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "ResendEmailAPI requires `httpx`. Install it or use "
                "FakeEmailAPI in tests."
            ) from e
        api_key = os.getenv("RESEND_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ResendEmailAPI requires RESEND_API_KEY to be set "
                "(in the environment or loaded from .env via load_dotenv())."
            )
        self._api_key = api_key

    def send_email(
        self,
        *,
        from_addr: str,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> str:
        import httpx

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(
                f"{self._base_url}/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_addr,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Resend send_email failed ({resp.status_code}): "
                f"{resp.text[:300]}"
            )
        data = resp.json() if resp.content else {}
        return str(data.get("id") or "")


@dataclass
class FakeEmailAPI:
    """In-memory ``EmailAPI`` for tests and dry-runs.

    Records every "sent" message so tests can assert on the call
    sequence. Never touches the network and requires no credentials.
    """

    sent: list[dict[str, Any]] = field(default_factory=list)
    next_id: int = 1

    def send_email(
        self,
        *,
        from_addr: str,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> str:
        eid = f"email-{self.next_id}"
        self.next_id += 1
        self.sent.append(
            {
                "from": from_addr,
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "id": eid,
            }
        )
        return eid


# ─── Subject + HTML derivation ──────────────────────────────────────────────


def _derive_subject(artifact: str, *, max_len: int = 78) -> str:
    """Use the first non-empty line of the artefact as the subject.

    Strips leading markdown header marks (``#``) and trailing
    whitespace; truncates to ``max_len`` (78 is the conventional soft
    limit for email subjects — anything longer is truncated by most
    clients anyway).
    """
    for line in artifact.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:max_len].rstrip()
    return "Message from the crew"


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def _to_html(artifact: str) -> str:
    """Render the artefact as a minimal HTML body.

    Splits on blank lines into paragraphs; wraps each in ``<p>``;
    HTML-escapes special characters. Within a paragraph, single
    newlines become ``<br>`` so the LLM's intended line breaks
    survive.

    Deliberately spartan — the message body IS the artefact, not a
    branded campaign template. The thesis demonstrates that the
    framework's role-driven LLM output reaches the inbox intact; a
    fuller HTML chrome belongs to a Passly-specific extension, not
    the framework.
    """
    paragraphs = _PARAGRAPH_BREAK.split(artifact.strip())
    rendered: list[str] = []
    for para in paragraphs:
        if not para.strip():
            continue
        escaped = (
            para.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        rendered.append(f"<p>{escaped}</p>")
    return "\n".join(rendered)


# ─── The tool itself ────────────────────────────────────────────────────────


@dataclass
class EmailTool:
    """Async callable suitable for ``ToolRegistry.register("email_tool", …)``.

    Construction args:

    - ``sender``: the ``from`` address. ``onboarding@resend.dev`` for
      sandbox; verified-domain address for production.
    - ``default_to``: recipient for this MVP scope (single address).
      Production / multi-recipient lands later (M4+).
    - ``subject_prefix``: optional, e.g. ``"[Passly] "``.
    - ``api``: an ``EmailAPI`` implementation; defaults to
      ``ResendEmailAPI()`` if not provided (which validates
      ``RESEND_API_KEY`` at construction).

    Calling ``await tool(artifact)`` derives the subject from the
    artefact's first line, renders the body as both plain text and
    HTML, and returns ``"sent:<email_id>:<recipient>"``.
    """

    sender: str
    default_to: str | None = None
    subject_prefix: str = ""
    api: EmailAPI | None = None

    def __post_init__(self) -> None:
        if not self.sender or "@" not in self.sender:
            raise RuntimeError(
                f"EmailTool requires sender in '<email>' or "
                f"'Name <email>' form; got {self.sender!r}"
            )
        if self.api is None:
            self.api = ResendEmailAPI()

    async def __call__(self, artifact: str) -> str:
        if not self.default_to:
            raise RuntimeError(
                "EmailTool needs a recipient. Set default_to= at "
                "construction or SFC_EMAIL_TO env var via "
                "make_email_tool()."
            )
        subject = self.subject_prefix + _derive_subject(artifact)
        text_body = artifact if artifact.endswith("\n") else artifact + "\n"
        html_body = _to_html(artifact)

        api = self.api
        assert api is not None  # set in __post_init__
        email_id = api.send_email(
            from_addr=self.sender,
            to=self.default_to,
            subject=subject,
            html=html_body,
            text=text_body,
        )
        return f"sent:{email_id}:{self.default_to}"


# ─── Provider registry ──────────────────────────────────────────────────────
#
# The default provider is Resend; the registry exists so a project can
# add SMTP / SendGrid / Mailgun / SES / etc. without modifying
# ``EmailTool`` or this module. Adding a provider is two lines:
#
#     class MyEmailAPI: ...  (implement send_email)
#     register_email_provider("myprovider", MyEmailAPI)
#
# After that, ``SFC_EMAIL_PROVIDER=myprovider`` (or
# ``make_email_tool(provider="myprovider")``) routes through it.


_PROVIDERS: dict[str, EmailProviderFactory] = {
    "resend": ResendEmailAPI,
}


def register_email_provider(name: str, factory: EmailProviderFactory) -> None:
    """Register an ``EmailAPI`` factory under ``name``.

    The factory must be callable with no arguments and return an
    object satisfying the :class:`EmailAPI` Protocol. Typically the
    factory is the class itself, but it can be any zero-arg callable
    — e.g. ``functools.partial(SmtpEmailAPI, server="smtp.gmail.com")``
    for a pre-bound configuration.

    Re-registering an existing name replaces the previous factory.
    Names are normalised to lower-case so ``"Resend"`` and ``"resend"``
    map to the same provider.
    """
    if not name:
        raise ValueError("provider name must be a non-empty string")
    _PROVIDERS[name.lower()] = factory


def available_email_providers() -> tuple[str, ...]:
    """Names of providers currently registered. Sorted for stable output."""
    return tuple(sorted(_PROVIDERS))


def _resolve_provider(name: str) -> EmailProviderFactory:
    key = name.lower()
    if key not in _PROVIDERS:
        available = ", ".join(sorted(_PROVIDERS))
        raise RuntimeError(
            f"Unknown email provider {name!r}. Available: {available}. "
            f"Register more via "
            f"solo_founder_crew.adapters.email.register_email_provider(name, factory)."
        )
    return _PROVIDERS[key]


# ─── Factory ────────────────────────────────────────────────────────────────


def make_email_tool(
    *,
    sender: str | None = None,
    default_to: str | None = None,
    subject_prefix: str | None = None,
    provider: str | None = None,
    api: EmailAPI | None = None,
):
    """Factory mirroring ``make_github_pr_tool``.

    Reads from the environment when the corresponding argument is not
    passed:

    - ``SFC_EMAIL_FROM`` (required) — sender address.
    - ``SFC_EMAIL_TO`` (optional) — default recipient.
    - ``SFC_EMAIL_SUBJECT_PREFIX`` (optional) — e.g. ``"[Passly] "``.
    - ``SFC_EMAIL_PROVIDER`` (optional, default ``"resend"``) — which
      registered provider to instantiate. Ignored when ``api`` is
      passed explicitly (the explicit object wins; the registry is
      bypassed).

    If neither ``api`` nor a known provider name is given, falls back
    to ``"resend"`` for backward compatibility.
    """
    resolved_sender = sender or os.getenv("SFC_EMAIL_FROM", "")
    if not resolved_sender:
        raise RuntimeError(
            "make_email_tool requires sender (positional or "
            "SFC_EMAIL_FROM env var). For sandbox demonstration use "
            "'onboarding@resend.dev'."
        )
    resolved_to = default_to or os.getenv("SFC_EMAIL_TO") or None
    resolved_prefix = (
        subject_prefix
        if subject_prefix is not None
        else os.getenv("SFC_EMAIL_SUBJECT_PREFIX", "")
    )
    if api is None:
        provider_name = provider or os.getenv("SFC_EMAIL_PROVIDER", "resend")
        api = _resolve_provider(provider_name)()
    return EmailTool(
        sender=resolved_sender,
        default_to=resolved_to,
        subject_prefix=resolved_prefix,
        api=api,
    )
