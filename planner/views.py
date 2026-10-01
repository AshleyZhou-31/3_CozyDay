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