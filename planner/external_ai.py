"""Gemini API service for CozyDay's second AI feature.

Only cleaned user text and, when explicitly selected, that user's open
PlanItem titles are sent to Google. API keys stay in environment-backed Django
settings and are sent in a request header, never in the URL or page output.
"""

import logging
from urllib.parse import quote

import requests
from django.conf import settings

from .ai_planner import (
    AIOutputError,
    SYSTEM_INSTRUCTION,
    build_user_message,
    parse_response,
)

logger = logging.getLogger(__name__)


class ExternalAIError(Exception):
    """Base error with a message that is safe to show in the browser."""

    user_message = "The API planner could not complete your request."

    def __init__(self, user_message=None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


class ExternalAIConfigurationError(ExternalAIError):
    user_message = (
        "The API planner is not configured yet. Ask the site owner to add the "
        "Gemini API key."
    )


class ExternalAITemporaryError(ExternalAIError):
    user_message = "The external AI service is temporarily unavailable. Please try again."


class ExternalAIResponseError(ExternalAIError):
    user_message = "The external AI service did not return a usable plan. Try rewording your request."


def _extract_text(payload):
    """Extract text from a Gemini generateContent response."""
    candidates = payload.get("candidates") or []
    if not candidates:
        block_reason = (payload.get("promptFeedback") or {}).get("blockReason")
        if block_reason:
            raise ExternalAIResponseError(
                "The external AI service could not process that request. Please reword it."
            )
        raise ExternalAIResponseError()

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not text.strip():
        raise ExternalAIResponseError()
    return text


def generate_external_plan(request_text, plan_items=None, request_post=None):
    """Call Gemini and return the same structured PlannerResult as the local model.

    ``request_post`` is injectable so tests never contact the real service.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ExternalAIConfigurationError()

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash-lite")
    timeout = getattr(settings, "GEMINI_API_TIMEOUT_SECONDS", 20)
    user_message = build_user_message(request_text, plan_items)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{quote(model, safe='-._')}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 256,
        },
    }
    post = request_post or requests.post

    try:
        response = post(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            json=payload,
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise ExternalAITemporaryError(
            "The external AI request timed out. Please try again."
        ) from exc
    except requests.RequestException as exc:
        logger.warning("Gemini API connection failed: %s", type(exc).__name__)
        raise ExternalAITemporaryError() from exc

    if response.status_code in (401, 403):
        raise ExternalAIConfigurationError(
            "The API planner credentials were rejected. Ask the site owner to check the Gemini API key."
        )
    if response.status_code == 429:
        raise ExternalAITemporaryError(
            "The external AI service is busy or its quota was reached. Please try again later."
        )
    if not 200 <= response.status_code < 300:
        raise ExternalAITemporaryError()

    try:
        raw_text = _extract_text(response.json())
        return parse_response(raw_text)
    except ValueError as exc:
        raise ExternalAIResponseError() from exc
    except AIOutputError as exc:
        raise ExternalAIResponseError(exc.user_message) from exc
