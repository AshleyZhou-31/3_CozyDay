from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView

from django.db.models import Count
from .models import Category, PlanItem


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
