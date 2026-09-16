from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views import View
from django.views.generic import ListView

from .models import PlanItem


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