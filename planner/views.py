from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import DetailView, ListView
from django.http import JsonResponse

from .models import PlanItem


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