"""Aggregations for the cost and token widgets on the system analytics page.

Everything here works on ``AIPerformanceEvent`` rows (counts, timings and
estimated dollars only) and returns plain values for the template. Costs are
estimates: tokens multiplied by an assumed price per 1,000 tokens.
"""
import statistics
from decimal import Decimal

from django.conf import settings

from .models import AIPerformanceEvent

UNRECORDED = "Not recorded"


def format_usd(value):
    if value is None:
        return "—"
    return f"${Decimal(value):.6f}"


def _mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def _category_label(key):
    if key is None:
        return "Uncategorized"
    return dict(AIPerformanceEvent.QueryCategory.choices).get(key, key)


def build_cost_context(events):
    """Return the template context for the cost section from a list of events."""
    costed = [e for e in events if e.estimated_cost_usd is not None]
    total_cost = sum((Decimal(e.estimated_cost_usd) for e in costed), Decimal("0"))
    mean_cost = total_cost / len(costed) if costed else None
    input_tokens = sum(e.input_tokens_estimate or 0 for e in costed)
    output_tokens = sum(e.output_tokens_estimate or 0 for e in costed)
    generated = [
        e for e in events
        if e.outcome == AIPerformanceEvent.Outcome.SUCCESS and e.generation_latency_ms is not None
    ]
    mean_generation = _mean(e.generation_latency_ms for e in generated)

    keys = [key for key, _ in AIPerformanceEvent.QueryCategory.choices] + [None]
    category_rows = []
    for key in keys:
        rows = [e for e in costed if e.query_category == key]
        cost = sum((Decimal(e.estimated_cost_usd) for e in rows), Decimal("0"))
        gen = [e for e in rows
               if e.outcome == AIPerformanceEvent.Outcome.SUCCESS
               and e.generation_latency_ms is not None]
        category_rows.append({
            "label": _category_label(key),
            "count": len(rows),
            "total_cost": cost,
            "total_cost_text": format_usd(cost),
            "mean_cost_text": format_usd(cost / len(rows)) if rows else "—",
            "input_tokens": sum(e.input_tokens_estimate or 0 for e in rows),
            "output_tokens": sum(e.output_tokens_estimate or 0 for e in rows),
            "mean_generation_ms": (
                round(_mean(e.generation_latency_ms for e in gen)) if gen else None
            ),
            "mean_output_tokens": (
                round(_mean(e.output_tokens_estimate for e in gen)) if gen else None
            ),
        })
    max_cost = max((row["total_cost"] for row in category_rows), default=Decimal("0"))
    max_tokens = max((row["input_tokens"] + row["output_tokens"] for row in category_rows), default=0)
    for row in category_rows:
        row["cost_width"] = float(row["total_cost"] / max_cost * 100) if max_cost else 0
        tokens = row["input_tokens"] + row["output_tokens"]
        row["token_width"] = tokens / max_tokens * 100 if max_tokens else 0
        row["token_total"] = tokens

    groups = {}
    for event in events:
        key = (event.serving_backend or UNRECORDED, event.model_name or UNRECORDED)
        groups.setdefault(key, []).append(event)
    backend_rows = []
    for (backend, model), rows in sorted(groups.items()):
        gen = [e.generation_latency_ms for e in rows
               if e.outcome == AIPerformanceEvent.Outcome.SUCCESS
               and e.generation_latency_ms is not None]
        cost_rows = [e for e in rows if e.estimated_cost_usd is not None]
        cost = sum((Decimal(e.estimated_cost_usd) for e in cost_rows), Decimal("0"))
        mean_total = _mean(e.total_latency_ms for e in rows)
        backend_rows.append({
            "backend": backend,
            "model": model,
            "count": len(rows),
            "mean_latency_ms": round(mean_total) if mean_total is not None else None,
            "mean_generation_ms": round(_mean(gen)) if gen else None,
            "mean_cost_text": format_usd(cost / len(cost_rows)) if cost_rows else "—",
        })

    return {
        "cost_has_data": bool(costed),
        "total_cost_text": format_usd(total_cost) if costed else "—",
        "mean_cost_text": format_usd(mean_cost),
        "total_tokens": input_tokens + output_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "mean_generation_ms": round(mean_generation) if mean_generation is not None else None,
        "cost_category_rows": category_rows,
        "backend_rows": backend_rows,
        "simulated_count": sum(bool(e.is_simulated) for e in events),
        "price_input_per_1k": getattr(settings, "AI_COST_INPUT_USD_PER_1K", None),
        "price_output_per_1k": getattr(settings, "AI_COST_OUTPUT_USD_PER_1K", None),
    }
