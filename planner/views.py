from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView
from django.http import JsonResponse, HttpResponseForbidden

from django.db.models import Count, Q
from .models import AIPerformanceEvent, Category, PlanItem
from .plan_templates import TEMPLATE_TYPES, detect_plan_type, parse_structured_plan
from .forms import AIPlannerForm, AIRAGPlannerForm, PlanItemForm
from .ai_planner import AIPlannerError, generate_plan
from .external_ai import ExternalAIError, generate_external_plan
from .rag_planner import generate_rag_plan

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from django.utils import timezone
import csv
import json
import requests
import logging
import math
import statistics
import time

from django.contrib.auth import get_user_model
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

def home(request):
    """Render the CozyDay landing page."""
    return render(request, "planner/home.html")

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("planner:planitem-list")
    else:
        form = UserCreationForm()

    return render(
        request,
        "planner/signup.html",
        {"form": form},
    )


# View 1: FBV, manual HttpResponse
@login_required
def planitem_list_manual(request):
    template = loader.get_template("planner/planitem_list.html")
    items = PlanItem.objects.filter(user=request.user)
    context = {"items": items}
    return HttpResponse(template.render(context, request))


# View 2: FBV, render() shortcut
@login_required
def planitem_list_render(request):
    items = PlanItem.objects.filter(user=request.user)
    context = {"items": items}
    return render(request, "planner/planitem_list.html", context)


# View 3: CBV, base View
class PlanItemListBaseView(LoginRequiredMixin, View):
    def get(self, request):
        items = PlanItem.objects.filter(user=request.user)
        context = {"items": items}
        return render(request, "planner/planitem_list.html", context)


# View 4: CBV, generic ListView
class PlanItemListView(LoginRequiredMixin, ListView):
    model = PlanItem
    template_name = "planner/planitem_list.html"
    context_object_name = "items"

    def get_queryset(self):
        queryset = PlanItem.objects.filter(user=self.request.user)

        title = self.request.GET.get("title", "").strip()

        if title:
            queryset = queryset.filter(title__icontains=title)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PlanItemForm(
            user=self.request.user if self.request.user.is_authenticated else None
        )
        context["search_title"] = self.request.GET.get("title", "")
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("admin:login")

        form = PlanItemForm(request.POST, user=request.user)

        if form.is_valid():
            plan_item = form.save(commit=False)
            plan_item.user = request.user
            plan_item.save()
            return redirect("planner:planitem-list")

        self.object_list = self.get_queryset()
        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)




class PlanItemDetailView(LoginRequiredMixin, DetailView):
    model = PlanItem
    template_name = "planner/planitem_detail.html"
    context_object_name = "item"

    def get_queryset(self):
        return PlanItem.objects.filter(user=self.request.user)

@login_required
def planitem_search(request):
    """
    Section 2: full list, GET search, POST search, a relationship-spanning
    filter through Category, a total count, and a grouped summary.
    """
    items = PlanItem.objects.filter(user=request.user)

    get_title = request.GET.get("title", "").strip()
    category_query = request.GET.get("category", "").strip()
    post_title = ""

    if request.method == "POST":
        post_title = request.POST.get("title", "").strip()
        if post_title:
            items = items.filter(title__icontains=post_title)
    elif get_title:
        items = items.filter(title__icontains=get_title)

    if category_query:
        items = items.filter(category__name__icontains=category_query)

    total_count = PlanItem.objects.filter(user=request.user).count()

    category_summary = (
        Category.objects.filter(user=request.user)
        .annotate(
            item_count=Count(
                "plan_items",
                filter=Q(plan_items__user=request.user),
            )
        )
        .order_by("-item_count", "name")
    )

    context = {
        "items": items,
        "get_title": get_title,
        "post_title": post_title,
        "category_query": category_query,
        "total_count": total_count,
        "category_summary": category_summary,
    }
    return render(request, "planner/planitem_search.html", context)

@login_required
def plan_items_api(request):
    plan_items = PlanItem.objects.filter(user=request.user)

    category = request.GET.get('category')
    if category:
        plan_items = plan_items.filter(category__name__iexact=category)

    completed = request.GET.get('completed')
    if completed is not None:
        is_completed = completed.lower() == 'true'
        plan_items = plan_items.filter(is_completed=is_completed)

    data = []
    for item in plan_items:
        data.append({
            "id": item.id,
            "title": item.title,
            "item_type": item.item_type,
            "timing": item.timing,
            "is_completed": item.is_completed,
            "category": item.category.name if item.category else None,
        })

    return JsonResponse({"results": data})

@login_required
def category_chart_png(request):
    """Return a bar chart of PlanItem counts per Category as a PNG image."""
    rows = (
        Category.objects.filter(user=request.user)
        .annotate(
            item_count=Count(
                "plan_items",
                filter=Q(plan_items__user=request.user),
            )
        )
        .order_by("-item_count", "name")
    )
    names = [row.name for row in rows]
    counts = [row.item_count for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.bar(names, counts, label="Plan items")
    ax.set_title("Plan Items per Category")
    ax.set_xlabel("Category")
    ax.set_ylabel("Number of plan items")
    ax.legend()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)

    return HttpResponse(buffer.getvalue(), content_type="image/png")

@login_required
def analytics(request):
    """Page that embeds the category chart."""
    return render(request, "planner/analytics.html")


def _percentile(values, percentile):
    """Return an interpolated percentile for a non-empty sequence."""
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


# Checked in this fixed order; first match wins. Order matches Ashley's
# specified category list exactly, so precedence is unambiguous and
# documented. Case-insensitive. Only ever called on cleaned, validated
# input; the raw query itself is never stored, only the returned label.
_QUERY_CATEGORY_KEYWORDS = [
    (AIPerformanceEvent.QueryCategory.TASK_BREAKDOWN, (
        "break down", "breakdown", "break it down", "steps", "subtask",
        "sub-task", "smaller tasks", "milestone",
    )),
    (AIPerformanceEvent.QueryCategory.PRIORITIZATION, (
        "priorit", "urgent", "most important", "what to work on first",
        "what should i work on", "which should i do first", "deadline",
    )),
    (AIPerformanceEvent.QueryCategory.STUDY_PLANNING, (
        "study", "exam", "spaced review", "spaced repetition", "revise",
        "revision",
    )),
    (AIPerformanceEvent.QueryCategory.PRIVACY_SHARING, (
        "share", "sharing", "private", "privacy", "teammate",
        "group project", "expose",
    )),
    (AIPerformanceEvent.QueryCategory.PROGRESS_REPORTING, (
        "progress", "report", "analytics", "completion", "completed",
        "weekly report",
    )),
]


def categorize_query(query):
    """Deterministically bucket a validated query into a fixed category.

    Case-insensitive keyword match against a documented precedence order;
    returns QueryCategory.OTHER when nothing matches, or None for empty
    input. The raw query text is never persisted -- only this label is.
    """
    if not isinstance(query, str) or not query.strip():
        return None
    lowered = query.lower()
    for category, keywords in _QUERY_CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return AIPerformanceEvent.QueryCategory.OTHER


def _record_ai_performance(*, outcome, started_at, result=None, validation_ms=0, query=None, template_type=None):
    """Persist aggregate timings only; logging failures must not break answers."""
    result = result if isinstance(result, dict) else {}
    stage_latencies = result.get("stage_latencies") or {}
    chunks = result.get("retrieved_chunks") or []
    scores = [
        float(chunk["score"])
        for chunk in chunks
        if isinstance(chunk, dict)
        and isinstance(chunk.get("score"), (int, float))
        and math.isfinite(chunk["score"])
    ]

    def milliseconds(seconds):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
            return None
        return max(0, round(seconds * 1000))

    query_length_chars = min(len(query), 32767) if isinstance(query, str) else None
    query_category = categorize_query(query)
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}

    try:
        AIPerformanceEvent.objects.create(
            outcome=outcome,
            total_latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
            embedding_latency_ms=milliseconds(stage_latencies.get("embedding")),
            retrieval_latency_ms=milliseconds(stage_latencies.get("retrieval")),
            generation_latency_ms=milliseconds(stage_latencies.get("generation")),
            validation_latency_ms=max(0, int(validation_ms)),
            max_similarity_score=max(scores) if scores else None,
            retrieved_count=min(len(chunks), 65535),
            query_length_chars=query_length_chars,
            query_category=query_category,
            template_type=template_type,
            input_tokens_estimate=usage.get("input_tokens"),
            output_tokens_estimate=usage.get("output_tokens"),
            estimated_cost_usd=usage.get("estimated_cost_usd"),
            model_name=usage.get("model_name") or "",
            serving_backend=usage.get("serving_backend") or "",
        )
    except Exception as exc:
        # Analytics persistence is best-effort and must not expose a user's prompt.
        logger.warning("Could not persist AI performance event (%s)", type(exc).__name__)


@login_required
def system_analytics(request):
    """Staff-only aggregate dashboard for privacy-minimal RAG performance data."""
    if not request.user.is_staff:
        return HttpResponseForbidden("Staff access is required to view system analytics.")

    from datetime import timedelta

    now = timezone.now()
    events = list(
        AIPerformanceEvent.objects.filter(created_at__gte=now - timedelta(days=30))
    )
    latencies = [event.total_latency_ms for event in events]
    mean_latency = statistics.fmean(latencies) if latencies else None
    median_latency = statistics.median(latencies) if latencies else None
    p95_latency = _percentile(latencies, .95)

    outcomes = [
        {"key": key, "label": label, "count": sum(e.outcome == key for e in events)}
        for key, label in AIPerformanceEvent.Outcome.choices
    ]
    outcome_total = len(events)
    for outcome in outcomes:
        outcome["percent"] = (outcome["count"] / outcome_total * 100) if outcome_total else 0

    stage_specs = [
        ("Embedding", "embedding_latency_ms"),
        ("Retrieval", "retrieval_latency_ms"),
        ("Generation", "generation_latency_ms"),
        ("Validation", "validation_latency_ms"),
    ]
    stages = []
    for label, field in stage_specs:
        values = [getattr(event, field) for event in events if getattr(event, field) is not None]
        stages.append({"label": label, "mean": statistics.fmean(values) if values else None})
    stage_max = max((stage["mean"] or 0 for stage in stages), default=0)
    for stage in stages:
        stage["width"] = (stage["mean"] / stage_max * 100) if stage_max and stage["mean"] is not None else 0

    daily = []
    for offset in range(13, -1, -1):
        day = (now - timedelta(days=offset)).date()
        day_events = [event for event in events if timezone.localtime(event.created_at).date() == day]
        daily.append({
            "label": f"{day.strftime('%b')} {day.day}",
            "mean": statistics.fmean(e.total_latency_ms for e in day_events) if day_events else None,
            "count": len(day_events),
        })
    trend_max = max((row["mean"] or 0 for row in daily), default=0)
    for row in daily:
        row["height"] = max(2, row["mean"] / trend_max * 100) if trend_max and row["mean"] is not None else 2

    usage_max = max((row["count"] for row in daily), default=0)
    for row in daily:
        row["usage_height"] = max(2, row["count"] / usage_max * 100) if usage_max else 2

    category_rows = [
        {"key": key, "label": label, "count": sum(e.query_category == key for e in events)}
        for key, label in AIPerformanceEvent.QueryCategory.choices
    ]
    uncategorized_count = sum(e.query_category is None for e in events)
    category_rows.append({"key": "uncategorized", "label": "Uncategorized", "count": uncategorized_count})
    for row in category_rows:
        row["percent"] = (row["count"] / outcome_total * 100) if outcome_total else 0

    comparison_rows = []
    for row in category_rows:
        if row["key"] == "uncategorized":
            cat_events = [e for e in events if e.query_category is None]
        else:
            cat_events = [e for e in events if e.query_category == row["key"]]
        lengths = [e.query_length_chars for e in cat_events if e.query_length_chars is not None]
        comparison_rows.append({
            "label": row["label"],
            "count": len(cat_events),
            "avg_length": round(sum(lengths) / len(lengths)) if lengths else None,
            "success": sum(e.outcome == AIPerformanceEvent.Outcome.SUCCESS for e in cat_events),
            "abstention": sum(e.outcome == AIPerformanceEvent.Outcome.ABSTENTION for e in cat_events),
            "error": sum(e.outcome == AIPerformanceEvent.Outcome.ERROR for e in cat_events),
        })

    context = {
        "event_count": outcome_total,
        "mean_latency": round(mean_latency) if mean_latency is not None else None,
        "median_latency": round(median_latency) if median_latency is not None else None,
        "p95_latency": round(p95_latency) if p95_latency is not None else None,
        "outcomes": outcomes,
        "stages": stages,
        "daily": daily,
        "category_rows": category_rows,
        "comparison_rows": comparison_rows,
        "success_rate": round(next((x["percent"] for x in outcomes if x["key"] == "success"), 0), 1),
        "abstention_rate": round(next((x["percent"] for x in outcomes if x["key"] == "abstention"), 0), 1),
        "error_rate": round(next((x["percent"] for x in outcomes if x["key"] == "error"), 0), 1),
        "has_events": bool(events),
    }
    return render(request, "planner/system_analytics.html", context)


PUBLIC_API_DEMO_USERNAME = "rishabh_demo"

@require_GET
def api_summary(request):
    """
    A5 Part 3: the one CozyDay API exposed publicly, without login.
    Returns clean, chart-ready JSON built from real CozyDay database rows
    (the shared demo account's data) for the Vega-Lite chart and the three
    alternative API use cases. No user_id or other account-identifying
    fields are included.
    """
    User = get_user_model()
    try:
        demo_user = User.objects.get(username=PUBLIC_API_DEMO_USERNAME)
    except User.DoesNotExist:
        response = JsonResponse({"category_counts": [], "activity_over_time": []})
        response["Access-Control-Allow-Origin"] = "*"
        return response

    category_counts = list(
        Category.objects.filter(user=demo_user)
        .annotate(
            item_count=Count(
                "plan_items",
                filter=Q(plan_items__user=demo_user),
            )
        )
        .order_by("-item_count", "name")
        .values("name", "item_count")
    )

    activity_rows = (
        PlanItem.objects.filter(user=demo_user)
        .exclude(scheduled_date__isnull=True)
        .values("scheduled_date")
        .annotate(count=Count("id"))
        .order_by("scheduled_date")
    )

    activity_over_time = [
        {"date": row["scheduled_date"].isoformat(), "count": row["count"]}
        for row in activity_rows
    ]

    response = JsonResponse({
        "category_counts": category_counts,
        "activity_over_time": activity_over_time,
    })
    response["Access-Control-Allow-Origin"] = "*"
    return response

@login_required
def chart_category_summary(request):
    """Page embedding the Vega-Lite bar chart of plan items per category."""
    return render(request, "planner/chart_category_summary.html")

@login_required
def chart_activity_over_time(request):
    """Page embedding the Vega-Lite line/scatter chart of plan items by date."""
    return render(request, "planner/chart_activity_over_time.html")

@login_required
def vega_chart1_png(request):
    """Dedicated PNG output matching the category-summary chart."""
    rows = (
        Category.objects.filter(user=request.user)
        .annotate(
            item_count=Count(
                "plan_items",
                filter=Q(plan_items__user=request.user),
            )
        )
        .order_by("-item_count", "name")
    )

    names = [row.name for row in rows]
    counts = [row.item_count for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.bar(names, counts, color="#704b2f")
    ax.set_title("Plan Items per Category")
    ax.set_xlabel("Category")
    ax.set_ylabel("Number of plan items")

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return HttpResponse(buffer.getvalue(), content_type="image/png")

@login_required
def vega_chart2_png(request):
    """Dedicated PNG output matching the activity-over-time chart."""
    rows = (
        PlanItem.objects.filter(user=request.user)
        .exclude(scheduled_date__isnull=True)
        .values("scheduled_date")
        .annotate(count=Count("id"))
        .order_by("scheduled_date")
    )

    dates = [row["scheduled_date"] for row in rows]
    counts = [row["count"] for row in rows]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.plot(dates, counts, marker="o", color="#704b2f")
    ax.set_title("Plan Items by Scheduled Date")
    ax.set_xlabel("Scheduled date")
    ax.set_ylabel("Number of plan items")
    fig.autofmt_xdate()

    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
def export_plan_items_csv(request):
    """A4 Part 3: downloadable CSV of all PlanItems, ordered consistently."""
    items = (
        PlanItem.objects.filter(user=request.user)
        .select_related("category")
        .order_by(
            "is_completed", "scheduled_date", "scheduled_time", "title"
        )
    )

    timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"planitems_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "id", "title", "item_type", "timing", "scheduled_date",
        "scheduled_time", "is_completed", "category", "notes",
        "created_at", "updated_at",
    ])
    for item in items:
        writer.writerow([
            item.id,
            item.title,
            item.item_type,
            item.timing,
            item.scheduled_date.isoformat() if item.scheduled_date else "",
            item.scheduled_time.isoformat() if item.scheduled_time else "",
            item.is_completed,
            item.category.name if item.category else "",
            item.notes,
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        ])
    return response



@login_required
def export_plan_items_json(request):
    """A4 Part 3: downloadable pretty-printed JSON of all PlanItems."""
    items = (
        PlanItem.objects.filter(user=request.user)
        .select_related("category")
        .order_by(
            "is_completed", "scheduled_date", "scheduled_time", "title"
        )
    )

    plan_items = [
        {
            "id": item.id,
            "title": item.title,
            "item_type": item.item_type,
            "timing": item.timing,
            "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
            "scheduled_time": item.scheduled_time.isoformat() if item.scheduled_time else None,
            "is_completed": item.is_completed,
            "category": item.category.name if item.category else None,
            "notes": item.notes,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }
        for item in items
    ]

    payload = {
        "generated_at": timezone.now().isoformat(),
        "record_count": len(plan_items),
        "plan_items": plan_items,
    }

    timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"planitems_{timestamp}.json"

    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def reports(request):
    """A4 Part 3: grouped summaries, totals, and download links."""
    category_summary = (
        Category.objects.filter(user=request.user)
        .annotate(
            item_count=Count(
                "plan_items",
                filter=Q(plan_items__user=request.user),
            )
        )
        .order_by("-item_count", "name")
    )

    user_items = PlanItem.objects.filter(user=request.user)

    status_summary = (
        user_items.values("item_type", "is_completed")
        .annotate(item_count=Count("id"))
        .order_by("item_type", "is_completed")
    )

    context = {
        "category_summary": category_summary,
        "status_summary": status_summary,
        "total_items": user_items.count(),
        "total_completed": user_items.filter(is_completed=True).count(),
    }
    return render(request, "planner/reports.html", context)


@login_required
def external_book_search_api(request):
    """
    A4 Part 2:
    Query Open Library, process the response,
    and compare it with CozyDay PlanItem data.
    """
    query = request.GET.get("q", "").strip()

    # Handle a missing query
    if not query:
        return JsonResponse(
            {
                "error": "Missing query parameter.",
                "example": "?q=study",
            },
            status=400,
        )

    try:
        response = requests.get(
            "https://openlibrary.org/search.json",
            params={"q": query},
            timeout=5,
        )

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.Timeout:
        return JsonResponse(
            {"error": "The external API request timed out."},
            status=504,
        )

    except requests.exceptions.ConnectionError:
        return JsonResponse(
            {"error": "Could not connect to the external API."},
            status=502,
        )

    except requests.exceptions.HTTPError:
        return JsonResponse(
            {"error": "The external API returned an HTTP error."},
            status=502,
        )

    except ValueError:
        return JsonResponse(
            {"error": "The external API returned invalid JSON."},
            status=502,
        )

    docs = data.get("docs", [])

    cozyday_match_count = PlanItem.objects.filter(
        user=request.user,
        title__icontains=query,
    ).count()

    # Handle no external results
    if not docs:
        return JsonResponse(
            {
                "query": query,
                "external_results": [],
                "cozyday_match_count": cozyday_match_count,
                "message": "No external results found.",
            }
        )

    # Keep only a small, consistent set of useful fields
    external_results = []

    for book in docs[:5]:
        external_results.append(
            {
                "title": book.get("title"),
                "author": (
                    book.get("author_name", [None])[0]
                    if book.get("author_name")
                    else None
                ),
                "first_publish_year": book.get("first_publish_year"),
            }
        )

    return JsonResponse(
        {
            "query": query,
            "external_results": external_results,
            "cozyday_match_count": cozyday_match_count,
        }
    )


@login_required
def ai_planner(request):
    """Local-model planning suggestion from free text (and optionally plan items)."""
    result = None
    error_message = ""

    if request.method == "POST":
        form = AIPlannerForm(request.POST)
        if form.is_valid():
            titles = []
            if form.cleaned_data["include_plan_items"]:
                titles = list(
                    PlanItem.objects.filter(user=request.user, is_completed=False)
                    .values_list("title", flat=True)[:settings.AI_PLANNER_MAX_PLAN_ITEMS]
                )
            try:
                result = generate_plan(form.cleaned_data["request_text"], titles)
            except AIPlannerError as exc:
                error_message = exc.user_message
    else:
        form = AIPlannerForm()

    return render(
        request,
        "planner/ai_planner.html",
        {"form": form, "result": result, "error_message": error_message},
    )


@login_required
def api_ai_planner(request):
    """External Gemini planning suggestion with explicit, minimal data sharing."""
    result = None
    error_message = ""

    if request.method == "POST":
        form = AIPlannerForm(request.POST)
        if form.is_valid():
            titles = []
            if form.cleaned_data["include_plan_items"]:
                titles = list(
                    PlanItem.objects.filter(user=request.user, is_completed=False)
                    .values_list("title", flat=True)[:settings.AI_PLANNER_MAX_PLAN_ITEMS]
                )
            try:
                result = generate_external_plan(
                    form.cleaned_data["request_text"], titles
                )
            except ExternalAIError as exc:
                error_message = exc.user_message
    else:
        form = AIPlannerForm()

    return render(
        request,
        "planner/external_ai_planner.html",
        {"form": form, "result": result, "error_message": error_message},
    )


@login_required
def ai_rag_planner(request):
    """Render the authenticated user flow for the local RAG planning assistant."""
    result = None
    error_message = ""

    if request.method == "POST":
        request_started = time.perf_counter()
        form = AIRAGPlannerForm(request.POST)
        if form.is_valid():
            template_type = detect_plan_type(form.cleaned_data["query"])
            validation_started = None
            try:
                result = generate_rag_plan(
                    form.cleaned_data["query"], user=request.user, template_type=template_type
                )
                validation_started = time.perf_counter()
                if (
                    not isinstance(result, dict)
                    or not isinstance(result.get("answer"), str)
                    or not result["answer"].strip()
                ):
                    raise ValueError("Invalid RAG response schema")
                if not isinstance(result.get("retrieved_chunks"), list):
                    raise ValueError("Invalid RAG response schema")
                if result.get("template_type") not in TEMPLATE_TYPES:
                    raise ValueError("Invalid RAG response schema")
                if result.get("template_type") != template_type:
                    raise ValueError("Invalid RAG response schema")
                if (
                    getattr(settings, "AI_PLANNER_OUTPUT_VALIDATION", True)
                    and result.get("outcome") != AIPerformanceEvent.Outcome.ABSTENTION
                ):
                    try:
                        parse_structured_plan(json.dumps(result.get("structured_plan")))
                    except (TypeError, ValueError):
                        raise ValueError("Invalid RAG response schema")
                if any(
                    not isinstance(chunk, dict)
                    or not isinstance(chunk.get("id"), str)
                    or not isinstance(chunk.get("text"), str)
                    or (
                        chunk.get("score") is not None
                        and not isinstance(chunk.get("score"), (int, float))
                    )
                    for chunk in result["retrieved_chunks"]
                ):
                    raise ValueError("Invalid RAG response schema")
                latency = result.get("latency_seconds")
                if (
                    not isinstance(latency, (int, float))
                    or not math.isfinite(latency)
                    or latency < 0
                ):
                    raise ValueError("Invalid RAG response schema")
                if (
                    result.get("warning") is not None
                    and not isinstance(result["warning"], str)
                ):
                    raise ValueError("Invalid RAG response schema")
                validation_ms = round((time.perf_counter() - validation_started) * 1000)
                outcome = result.get("outcome")
                if outcome not in (
                    AIPerformanceEvent.Outcome.SUCCESS,
                    AIPerformanceEvent.Outcome.ABSTENTION,
                ):
                    scores = [
                        chunk["score"]
                        for chunk in result["retrieved_chunks"]
                        if chunk.get("score") is not None
                    ]
                    threshold = getattr(settings, "AI_PLANNER_MIN_RELEVANCE", 0.35)
                    outcome = (
                        AIPerformanceEvent.Outcome.ABSTENTION
                        if scores and max(scores) < threshold
                        else AIPerformanceEvent.Outcome.SUCCESS
                    )
                _record_ai_performance(
                    outcome=outcome,
                    started_at=request_started,
                    result=result,
                    validation_ms=validation_ms,
                    query=form.cleaned_data["query"],
                    template_type=template_type,
                )
                result.setdefault("warning", None)
                result["query"] = form.cleaned_data["query"]
            except Exception as exc:
                # Do not log the exception text: it may contain the user's query.
                logger.error("RAG Planner service failed (%s)", type(exc).__name__)
                _record_ai_performance(
                    outcome=AIPerformanceEvent.Outcome.ERROR,
                    started_at=request_started,
                    query=form.cleaned_data.get("query"),
                    validation_ms=(
                        round((time.perf_counter() - validation_started) * 1000)
                        if validation_started is not None
                        else 0
                    ),
                    template_type=template_type,
                )
                result = None
                error_message = getattr(
                    exc,
                    "user_message",
                    "The planning assistant is temporarily unavailable. Please try again later.",
                )
        else:
            _record_ai_performance(
                outcome=AIPerformanceEvent.Outcome.ERROR,
                started_at=request_started,
            )
    else:
        form = AIRAGPlannerForm()

    return render(
        request,
        "planner/ai_rag_planner.html",
        {"form": form, "result": result, "error_message": error_message},
    )
