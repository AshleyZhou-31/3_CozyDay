"""Plan-type detection and structured prompt templates for the RAG planner.

The detector stores only a small template identifier. It never persists or logs
the user's request text.
"""
from __future__ import annotations

import json
import re


GENERAL = "general"
WEEKLY = "weekly"
MONTHLY = "monthly"
THREE_MONTH = "three_month"

TEMPLATE_TYPES = (GENERAL, WEEKLY, MONTHLY, THREE_MONTH)

_DETECTORS = (
    (THREE_MONTH, re.compile(r"\b(?:three|3)\s*[- ]?months?\b|\bquarter(?:ly)?\b|\b90[ -]?days?\b|\b12\s+weeks?\b", re.I)),
    (WEEKLY, re.compile(r"\b(?:weekly|this week|next week|week(?:ly)? plan|week|7[ -]?days?)\b", re.I)),
    (MONTHLY, re.compile(r"\b(?:monthly|this month|next month|month(?:ly)? plan|30[ -]?days?|four weeks?)\b", re.I)),
)

_COMMON = """Return exactly one valid JSON object, with no Markdown fences or text before or after it.
Use these exact keys and value types:
{
  "goal": "string",
  "time_period": "string",
  "priorities": ["string"],
  "tasks_or_phases": ["string"],
  "deadlines": ["string"],
  "recommended_next_steps": ["string"]
}
Use only the user's request and retrieved CozyDay guidance. Do not invent dates,
appointments, commitments, or personal facts. If the user did not specify a
deadline, return an empty deadlines list. Keep every item concise and actionable.
"""

PROMPT_TEMPLATES = {
    GENERAL: _COMMON + "Build a concise plan that matches the goal and timeframe the user actually provided. Do not assume a fixed planning horizon.",
    WEEKLY: _COMMON + "Create a one-week plan. Group tasks into days or a sensible weekly sequence. Include realistic pacing and one check-in, without assigning calendar dates the user did not provide.",
    MONTHLY: _COMMON + "Create a one-month plan. Organize tasks into weekly milestones and make dependencies clear. Do not assign calendar dates unless the user supplied them.",
    THREE_MONTH: _COMMON + "Create a three-month plan. Organize work into Month 1, Month 2, and Month 3 phases, with progress checks and dependencies. Do not assign calendar dates unless the user supplied them.",
}

_REQUIRED_KEYS = (
    "goal",
    "time_period",
    "priorities",
    "tasks_or_phases",
    "deadlines",
    "recommended_next_steps",
)
_LIST_KEYS = ("priorities", "tasks_or_phases", "deadlines", "recommended_next_steps")


def detect_plan_type(query: str) -> str:
    """Return a specialized plan type, or ``general`` for ambiguous requests."""
    text = query if isinstance(query, str) else ""
    for template_type, pattern in _DETECTORS:
        if pattern.search(text):
            return template_type
    return GENERAL


def get_template(template_type: str | None) -> str:
    """Select a prompt, safely falling back to the general template."""
    return PROMPT_TEMPLATES.get(template_type, PROMPT_TEMPLATES[GENERAL])


def parse_structured_plan(raw_text: str) -> dict:
    """Parse and validate the model's JSON plan, raising ``ValueError`` on failure."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("The response was not valid JSON.") from exc
    if not isinstance(payload, dict) or any(key not in payload for key in _REQUIRED_KEYS):
        raise ValueError("The response did not contain all required plan fields.")
    goal = payload["goal"]
    period = payload["time_period"]
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("The goal must be a non-empty string.")
    if not isinstance(period, str) or not period.strip():
        raise ValueError("The time period must be a non-empty string.")
    cleaned = {"goal": goal.strip(), "time_period": period.strip()}
    for key in _LIST_KEYS:
        value = payload[key]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{key} must be a list of strings.")
        cleaned[key] = [item.strip() for item in value if item.strip()]
    return cleaned


def format_structured_plan(plan: dict) -> str:
    """Render validated fields into concise, readable text for the existing page."""
    labels = (
        ("Goal", "goal"),
        ("Time period", "time_period"),
        ("Priorities", "priorities"),
        ("Tasks or phases", "tasks_or_phases"),
        ("Deadlines", "deadlines"),
        ("Recommended next steps", "recommended_next_steps"),
    )
    lines = []
    for label, key in labels:
        value = plan[key]
        if isinstance(value, list):
            lines.append(f"{label}:")
            lines.extend(f"- {item}" for item in value)
            if not value:
                lines.append("- None specified")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)
