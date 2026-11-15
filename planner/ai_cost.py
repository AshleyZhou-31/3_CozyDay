"""Token and cost estimation for CozyDay AI requests (A10 Stage 3).

Only counts and an estimated dollar amount are produced here. Prompt text,
answers and retrieved content are never stored or logged by this module.

The numbers are estimates:

* Primary cost metric (local compute): ``generation_seconds / 3600 x
  AI_HARDWARE_RATE_USD_PER_HOUR``. The model runs on CozyDay's own hardware, so
  the cost of a request is the time the hardware spends generating it at a
  configurable hourly rate (default $0.50/hour).
* Token counts are a separate usage metric. They come from the loaded model's
  tokenizer when one is available and are otherwise approximated as one token
  per four characters.
* Secondary cost metric (API-equivalent): ``tokens x an assumed price per 1,000
  tokens`` (``AI_COST_INPUT_USD_PER_1K`` and ``AI_COST_OUTPUT_USD_PER_1K``). It
  shows what the same usage might cost on a hosted API. It is not the actual
  cost of the local model and must be labelled as secondary wherever shown.

Every place that shows a dollar figure must label it "estimated".
"""
import math
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

CHARS_PER_TOKEN = 4
COST_QUANTUM = Decimal("0.00000001")  # matches DecimalField(decimal_places=8)
DEFAULT_BACKEND = "transformers-local"
DEFAULT_HARDWARE_RATE_USD_PER_HOUR = "0.50"


def count_tokens(text, tokenizer=None):
    """Return a token count for ``text``; never raises."""
    if not isinstance(text, str) or not text:
        return 0
    if tokenizer is not None:
        try:
            ids = tokenizer.encode(text)
        except Exception:
            ids = None
        if isinstance(ids, (list, tuple)):
            return len(ids)
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _price(name, default):
    try:
        value = Decimal(str(getattr(settings, name, default)))
    except Exception:
        return Decimal(str(default))
    return value if value >= 0 else Decimal(str(default))


def hardware_rate_usd_per_hour():
    """Configured hourly cost of the hardware that runs the model."""
    return _price("AI_HARDWARE_RATE_USD_PER_HOUR", DEFAULT_HARDWARE_RATE_USD_PER_HOUR)


def estimate_local_compute_cost(generation_seconds):
    """Primary estimate: ``generation_seconds / 3600 x hourly hardware rate``.

    Missing, negative or non-numeric times count as zero (for example, an
    abstention never calls the model), so this never raises.
    """
    try:
        seconds = Decimal(str(generation_seconds or 0))
    except Exception:
        seconds = Decimal(0)
    seconds = max(Decimal(0), seconds)
    cost = seconds / Decimal(3600) * hardware_rate_usd_per_hour()
    return cost.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP)


def estimate_api_equivalent_cost_usd(input_tokens, output_tokens):
    """Secondary estimate: tokens x an assumed API price, quantized to 8 places."""
    input_price = _price("AI_COST_INPUT_USD_PER_1K", "0.0002")
    output_price = _price("AI_COST_OUTPUT_USD_PER_1K", "0.0004")
    cost = (
        Decimal(max(0, int(input_tokens or 0))) * input_price
        + Decimal(max(0, int(output_tokens or 0))) * output_price
    ) / Decimal(1000)
    return cost.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP)


def serving_backend_label():
    value = getattr(settings, "AI_SERVING_BACKEND", DEFAULT_BACKEND)
    return value[:40] if isinstance(value, str) and value.strip() else DEFAULT_BACKEND


def model_name_label(generation_info=None):
    name = generation_info.get("model_name") if isinstance(generation_info, dict) else None
    if not isinstance(name, str) or not name.strip():
        name = getattr(settings, "AI_PLANNER_MODEL_ID", "")
    return name[:100] if isinstance(name, str) else ""


def build_usage(
    *, generated, system_instruction, chunks, query, answer,
    generation_info=None, generation_seconds=None,
):
    """Summarise one request's token use and estimated cost.

    ``estimated_cost_usd`` is the primary local-compute estimate based on
    ``generation_seconds``; ``api_equivalent_cost_usd`` is the secondary
    token-price estimate.

    ``generated`` is False when the relevance gate skipped generation: no model
    call happened, so tokens and cost are zero. Any failure returns ``None`` so
    that usage tracking can never break an answer.
    """
    try:
        tokenizer = generation_info.get("tokenizer") if isinstance(generation_info, dict) else None
        input_tokens = output_tokens = 0
        if not generated:
            generation_seconds = 0
        if generated:
            prompt_parts = [system_instruction or ""]
            prompt_parts.extend(
                chunk.get("text", "") for chunk in (chunks or []) if isinstance(chunk, dict)
            )
            prompt_parts.append(query or "")
            input_tokens = count_tokens("\n\n".join(prompt_parts), tokenizer)
            output_tokens = count_tokens(answer, tokenizer)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": estimate_local_compute_cost(generation_seconds),
            "api_equivalent_cost_usd": estimate_api_equivalent_cost_usd(
                input_tokens, output_tokens
            ),
            "model_name": model_name_label(generation_info),
            "serving_backend": serving_backend_label(),
        }
    except Exception:
        return None
