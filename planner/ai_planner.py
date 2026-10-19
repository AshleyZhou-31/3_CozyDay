"""Local Hugging Face model service for the CozyDay AI planner (Stage 3).

The selected model (``settings.AI_PLANNER_MODEL_ID``, default
``Qwen/Qwen2.5-3B-Instruct``) is loaded lazily on first use, cached in this
process, and queried with the same system instruction and few-shot examples that
were evaluated in ``llm-test/ai_prototype.ipynb``.

Design notes
------------
* ``torch`` and ``transformers`` are imported only inside functions, so Django
  (and the test suite) starts even when they are not installed. In that case
  the feature reports "unavailable" instead of crashing the page.
* Every failure is converted to an ``AIPlannerError`` subclass that carries a
  safe ``user_message``; views never see a raw traceback from the model.
* Generation uses ``max_time`` (a soft timeout) and ``max_new_tokens``.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class AIPlannerError(Exception):
    """Base class. ``user_message`` is safe to show to the user."""

    user_message = "The AI planner could not complete your request."

    def __init__(self, user_message=None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


class AIInputError(AIPlannerError):
    """The user's text is empty or too long."""


class AIUnavailableError(AIPlannerError):
    """Packages are missing or the model could not be loaded."""

    user_message = (
        "The local AI model is not available right now. Ask the site owner "
        "to check the AI setup instructions."
    )


class AIGenerationError(AIPlannerError):
    """The model failed while generating text."""

    user_message = "The AI model ran into a problem. Please try again."


class AIOutputError(AIPlannerError):
    """The model returned empty or unusable text."""

    user_message = (
        "The AI model did not return a usable plan. Try rewording your request."
    )


# --------------------------------------------------------------------------
# Prompt (identical to the notebook's evaluated SYSTEM_INSTRUCTION / shots)
# --------------------------------------------------------------------------
SYSTEM_INSTRUCTION = (
    "You are CozyDay, a helpful daily planning assistant. "
    "Use only the information provided by the user. "
    "Give realistic, concise, actionable planning advice. "
    "Do not invent deadlines or appointments. "
    "Use exactly these three headings:\n"
    "Priority:\n"
    "Schedule:\n"
    "Reason:"
)

SHOT_EXAMPLES = [
    {
        "input": "I have a dentist appointment at 10 AM, need to walk the dog, and want to read for 30 minutes.",
        "response": (
            "Priority: Dentist appointment at 10 AM\n"
            "Schedule:\n"
            "1. Walk the dog before 9:30 AM.\n"
            "2. Attend the dentist appointment at 10 AM.\n"
            "3. Read for 30 minutes after you return.\n"
            "Reason: The appointment is time-fixed, so the flexible tasks are placed around it."
        ),
    },
    {
        "input": "I need to pay bills, do laundry, and call my parents, but I only have 2 hours free tonight.",
        "response": (
            "Priority: Pay bills\n"
            "Schedule:\n"
            "1. Pay bills (20 minutes).\n"
            "2. Start laundry, then call your parents while it runs (45 minutes).\n"
            "3. Finish folding laundry (20 minutes).\n"
            "Reason: Bills often have deadlines and are prioritized first; the call is layered into idle laundry time to fit the 2-hour window."
        ),
    },
    {
        "input": "I have a 9 AM flight, need to pack, and want to check in online.",
        "response": (
            "Priority: Check in online\n"
            "Schedule:\n"
            "1. Check in online the night before.\n"
            "2. Pack the night before as well.\n"
            "3. Leave with enough buffer for a 9 AM flight.\n"
            "Reason: Check-in and packing should happen ahead of time since the flight time itself is fixed and non-negotiable."
        ),
    },
]


# --------------------------------------------------------------------------
# Preprocessing
# --------------------------------------------------------------------------
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁠﻿]")
_WHITESPACE = re.compile(r"\s+")


def _setting(name, default):
    return getattr(settings, name, default)


def clean_text(text):
    """Remove control characters and collapse all whitespace to single spaces."""
    if not isinstance(text, str):
        return ""
    return _WHITESPACE.sub(" ", _CONTROL_CHARS.sub(" ", text)).strip()


def clean_user_text(text, max_chars=None):
    """Validate and normalise the user's request.

    Raises ``AIInputError`` for empty input or text longer than ``max_chars``
    (we reject rather than silently truncate, so the user knows what was sent).
    """
    max_chars = max_chars or _setting("AI_PLANNER_MAX_INPUT_CHARS", 600)
    cleaned = clean_text(text)
    if not cleaned:
        raise AIInputError("Please describe what you need to plan before submitting.")
    if len(cleaned) > max_chars:
        raise AIInputError(
            f"Your request is {len(cleaned)} characters long; please keep it under {max_chars}."
        )
    return cleaned


def build_user_message(request_text, plan_items=None):
    """Combine the request with the user's own plan-item titles (if any)."""
    message = clean_user_text(request_text)
    titles = []
    for title in plan_items or []:
        title = clean_text(title)[:80]
        if title:
            titles.append(title)
    limit = _setting("AI_PLANNER_MAX_PLAN_ITEMS", 10)
    titles = titles[:limit]
    if titles:
        message = f"{message} My open plan items: " + "; ".join(titles) + "."
    return message


def build_prompt(tokenizer, user_message, n_shots=None):
    """Chat-template prompt with the shared system instruction and few-shot pairs."""
    if n_shots is None:
        n_shots = _setting("AI_PLANNER_FEW_SHOTS", 3)
    messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for example in SHOT_EXAMPLES[:n_shots]:
        messages.append({"role": "user", "content": example["input"]})
        messages.append({"role": "assistant", "content": example["response"]})
    messages.append({"role": "user", "content": user_message})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


# --------------------------------------------------------------------------
# Output parsing
# --------------------------------------------------------------------------
_HEADING = re.compile(
    r"^[ \t>#*_-]*(Priority|Schedule|Reason)[ \t]*\**[ \t]*:\**",
    re.IGNORECASE | re.MULTILINE,
)
_LEADING_MARKER = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


@dataclass
class PlannerResult:
    priority: str
    schedule: list = field(default_factory=list)
    reason: str = ""
    truncated: bool = False
    raw: str = ""

    @property
    def complete(self):
        return bool(self.priority and self.schedule and self.reason and not self.truncated)


def _clean_line(line):
    line = _LEADING_MARKER.sub("", line.strip())
    return line.replace("**", "").replace("__", "").strip()


def parse_response(raw_text, truncated=False):
    """Turn ``Priority:/Schedule:/Reason:`` text into a ``PlannerResult``.

    Raises ``AIOutputError`` when the text is empty or has no usable
    Priority and Schedule sections. A missing Reason (often caused by hitting
    the token limit) is tolerated and flagged via ``complete``.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise AIOutputError("The AI model returned an empty response. Please try again.")

    matches = list(_HEADING.finditer(raw_text))
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        name = match.group(1).lower()
        sections.setdefault(name, raw_text[match.end():end])

    def lines_for(name):
        body = sections.get(name, "")
        return [line for line in (_clean_line(l) for l in body.splitlines()) if line]

    priority_lines = lines_for("priority")
    schedule_lines = lines_for("schedule")
    reason_lines = lines_for("reason")

    if not priority_lines or not schedule_lines:
        raise AIOutputError()

    return PlannerResult(
        priority=" ".join(priority_lines),
        schedule=schedule_lines,
        reason=" ".join(reason_lines),
        truncated=truncated,
        raw=raw_text,
    )


# --------------------------------------------------------------------------
# Model loading and generation
# --------------------------------------------------------------------------
_model_cache = {}
_load_lock = threading.Lock()
_generate_lock = threading.Lock()


def _pick_device(torch):
    configured = str(_setting("AI_PLANNER_DEVICE", "auto")).lower()
    if configured != "auto":
        return configured
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _pick_dtype(torch, device):
    # fp16 on GPU/MPS; bfloat16 on CPU keeps the 3B model near 6 GB instead of 12 GB.
    return torch.float16 if device in ("cuda", "mps") else torch.bfloat16


def get_model(model_id=None):
    """Return a cached ``(tokenizer, model)`` pair, loading it on first use."""
    model_id = model_id or _setting("AI_PLANNER_MODEL_ID", "Qwen/Qwen2.5-3B-Instruct")
    cached = _model_cache.get(model_id)
    if cached:
        return cached

    with _load_lock:
        cached = _model_cache.get(model_id)
        if cached:
            return cached
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            logger.warning("AI planner packages are missing: %s", exc)
            raise AIUnavailableError() from exc

        try:
            device = _pick_device(torch)
            dtype = _pick_dtype(torch, device)
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            try:
                model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
            except TypeError:  # transformers < 4.56 uses torch_dtype
                model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype)
            model.to(device)
            model.eval()
        except Exception as exc:  # download, memory, license, device errors
            logger.exception("Could not load AI planner model %s", model_id)
            raise AIUnavailableError(
                "The local AI model could not be loaded (check the network, disk "
                "space and memory). Please try again later."
            ) from exc

        _model_cache[model_id] = (tokenizer, model)
        return tokenizer, model


def clear_model_cache():
    """Drop the cached model (used by tests)."""
    _model_cache.clear()


def generate_plan(request_text, plan_items=None):
    """Run the full pipeline and return a ``PlannerResult``."""
    user_message = build_user_message(request_text, plan_items)
    tokenizer, model = get_model()

    max_new_tokens = _setting("AI_PLANNER_MAX_NEW_TOKENS", 256)
    max_time = _setting("AI_PLANNER_MAX_TIME_SECONDS", 120)

    try:
        import torch

        prompt = build_prompt(tokenizer, user_message)
        inputs = tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to(model.device) for key, value in inputs.items()}

        started = time.perf_counter()
        with _generate_lock, torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                max_time=max_time,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        elapsed = time.perf_counter() - started

        new_tokens = output[0][inputs["input_ids"].shape[1]:]
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        truncated = len(new_tokens) >= max_new_tokens or elapsed >= max_time
    except AIPlannerError:
        raise
    except Exception as exc:
        logger.exception("AI planner generation failed")
        raise AIGenerationError() from exc

    return parse_response(raw_text, truncated=truncated)
