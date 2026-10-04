from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView
from django.http import JsonResponse

from django.db.models import Count
from .models import Category, PlanItem
from .forms import PlanItemForm

from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from django.utils import timezone
import csv
import requests

def home(request):
    """Render the CozyDay landing page."""
    return render(request, "planner/home.html")


# View 1: FBV, manual HttpResponse
def planitem_list_manual(request):
    template = loader.get_template("planner/planitem_list.html")
    items = PlanItem.objects.all()
    context = {"items": items}
    return HttpResponse(template.render(context, request))


# View 2: FBV, render() shortcut
def planitem_list_render(request):
    items = PlanItem.objects.all()
    context = {"items": items}
    return render(request, "planner/planitem_list.html", context)


# View 3: CBV, base View
class PlanItemListBaseView(View):
    def get(self, request):
        items = PlanItem.objects.all()
        context = {"items": items}
        return render(request, "planner/planitem_list.html", context)


# View 4: CBV, generic ListView
class PlanItemListView(ListView):
    model = PlanItem
    template_name = "planner/planitem_list.html"
    context_object_name = "items"

    def get_queryset(self):
        if self.request.user.is_authenticated:
            queryset = PlanItem.objects.filter(user=self.request.user)
        else:
            queryset = PlanItem.objects.all()

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




class PlanItemDetailView(DetailView):
    model = PlanItem
    template_name = "planner/planitem_detail.html"
    context_object_name = "item"

def planitem_search(request):
    """
    Section 2: full list, GET search, POST search, a relationship-spanning
    filter through Category, a total count, and a grouped summary.
    """
    items = PlanItem.objects.all()

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

    total_count = PlanItem.objects.count()

    category_summary = (
        Category.objects.annotate(item_count=Count("plan_items"))
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

def plan_items_api(request):
    plan_items = PlanItem.objects.all()

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

def category_chart_png(request):
    """Return a bar chart of PlanItem counts per Category as a PNG image."""
    rows = (
        Category.objects.annotate(item_count=Count("plan_items"))
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

def analytics(request):
    """Page that embeds the category chart."""
    return render(request, "planner/analytics.html")

def api_summary(request):
    """
    A4 Part 1: public, GET-only, chart-ready JSON built from real PlanItem
    and Category data. No writes, no auth required.
    """
    category_counts = list(
        Category.objects.annotate(item_count=Count("plan_items"))
        .order_by("-item_count", "name")
        .values("name", "item_count")
    )

    activity_rows = (
        PlanItem.objects.exclude(scheduled_date__isnull=True)
        .values("scheduled_date")
        .annotate(count=Count("id"))
        .order_by("scheduled_date")
    )
    activity_over_time = [
        {"date": row["scheduled_date"].isoformat(), "count": row["count"]}
        for row in activity_rows
    ]

    return JsonResponse({
        "category_counts": category_counts,
        "activity_over_time": activity_over_time,
    })


def chart_category_summary(request):
    """Page embedding the Vega-Lite bar chart of plan items per category."""
    return render(request, "planner/chart_category_summary.html")


def chart_activity_over_time(request):
    """Page embedding the Vega-Lite line/scatter chart of plan items by date."""
    return render(request, "planner/chart_activity_over_time.html")


def vega_chart1_png(request):
    """Dedicated PNG output matching the category-summary chart."""
    rows = (
        Category.objects.annotate(item_count=Count("plan_items"))
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


def vega_chart2_png(request):
    """Dedicated PNG output matching the activity-over-time chart."""
    rows = (
        PlanItem.objects.exclude(scheduled_date__isnull=True)
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

def export_plan_items_csv(request):
    """A4 Part 3: downloadable CSV of all PlanItems, ordered consistently."""
    items = PlanItem.objects.select_related("category").order_by(
        "is_completed", "scheduled_date", "scheduled_time", "title"
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


def export_plan_items_json(request):
    """A4 Part 3: downloadable pretty-printed JSON of all PlanItems."""
    items = PlanItem.objects.select_related("category").order_by(
        "is_completed", "scheduled_date", "scheduled_time", "title"
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


def reports(request):
    """A4 Part 3: grouped summaries, totals, and download links."""
    category_summary = (
        Category.objects.annotate(item_count=Count("plan_items"))
        .order_by("-item_count", "name")
    )

    status_summary = (
        PlanItem.objects.values("item_type", "is_completed")
        .annotate(item_count=Count("id"))
        .order_by("item_type", "is_completed")
    )

    context = {
        "category_summary": category_summary,
        "status_summary": status_summary,
        "total_items": PlanItem.objects.count(),
        "total_completed": PlanItem.objects.filter(is_completed=True).count(),
    }
    return render(request, "planner/reports.html", context)



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
        title__icontains=query
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