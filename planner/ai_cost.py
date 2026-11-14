"""Token and cost estimation for CozyDay AI requests (A10 Stage 3).

Only counts and an estimated dollar amount are produced here. Prompt text,
answers and retrieved content are never stored or logged by this module.

The numbers are estimates:

* Tokens are counted with the loaded model's tokenizer when one is available
  and otherwise approximated as one token per four characters.
* The dollar figure is ``tokens x an assumed price per 1,000 tokens``. A local
  model has no per-request bill, so the prices are configurable assumptions
  (``AI_COST_INPUT_USD_PER_1K`` and ``AI_COST_OUTPUT_USD_PER_1K``) and every
  place that shows the result must label it "estimated".
"""
import math
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

CHARS_PER_TOKEN = 4
COST_QUANTUM = Decimal("0.00000001")  # matches DecimalField(decimal_places=8)
DEFAULT_BACKEND = "transformers-local"


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


def estimate_cost_usd(input_tokens, output_tokens):
    """Estimated cost in USD for the given token counts, quantized to 8 places."""
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


def build_usage(*, generated, system_instruction, chunks, query, answer, generation_info=None):
    """Summarise one request's token use and estimated cost.

    ``generated`` is False when the relevance gate skipped generation: no model
    call happened, so tokens and cost are zero. Any failure returns ``None`` so
    that usage tracking can never break an answer.
    """
    try:
        tokenizer = generation_info.get("tokenizer") if isinstance(generation_info, dict) else None
        input_tokens = output_tokens = 0
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
            "estimated_cost_usd": estimate_cost_usd(input_tokens, output_tokens),
            "model_name": model_name_label(generation_info),
            "serving_backend": serving_backend_label(),
        }
    except Exception:
        return None
