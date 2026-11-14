"""Optional Sentry error monitoring (A10 Stage 3).

Sentry is off unless ``SENTRY_DSN`` is set in the environment. Without a DSN,
or without the ``sentry-sdk`` package installed, nothing is imported or sent
and the application runs exactly as before.

Privacy: events are scrubbed before they leave the server. Request bodies,
cookies, headers, query strings, user details, local variables and exception
messages (which could echo a planning question) are all removed. Only the
exception type, the stack frames' file and function names, and the request
method and path are kept.
"""
import logging
import os

logger = logging.getLogger(__name__)

SCRUBBED = "[removed]"


def _rate(value, default=0.0):
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return default
    return rate if 0.0 <= rate <= 1.0 else default


def scrub_event(event, hint=None):
    """Remove anything that could contain user-written text or identity."""
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = {
            key: request[key] for key in ("method", "url") if key in request
        }
        url = event["request"].get("url")
        if isinstance(url, str):
            event["request"]["url"] = url.split("?", 1)[0]
    event.pop("user", None)
    event.pop("extra", None)
    event.pop("breadcrumbs", None)
    for entry in (event.get("exception") or {}).get("values", []) or []:
        if isinstance(entry, dict) and entry.get("value"):
            entry["value"] = SCRUBBED
    if event.get("logentry"):
        event["logentry"] = {"message": SCRUBBED}
    if event.get("message"):
        event["message"] = SCRUBBED
    return event


def init_sentry(environ=None):
    """Start Sentry when configured. Returns True only if it was started."""
    environ = os.environ if environ is None else environ
    dsn = (environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; monitoring is off.")
        return False
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environ.get("SENTRY_ENVIRONMENT") or "production",
            traces_sample_rate=_rate(environ.get("SENTRY_TRACES_SAMPLE_RATE")),
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            before_send=scrub_event,
        )
    except Exception:
        logger.warning("Sentry could not be started; monitoring is off.")
        return False
    return True
