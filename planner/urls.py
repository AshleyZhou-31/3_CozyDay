from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("", views.PlanItemListView.as_view(), name="planitem-list"),
    path("manual/", views.planitem_list_manual, name="planitem-manual"),
    path("render/", views.planitem_list_render, name="planitem-render"),
    path("cbv-base/", views.PlanItemListBaseView.as_view(), name="planitem-cbv-base"),
    path("cbv-generic/", views.PlanItemListView.as_view(), name="planitem-cbv-generic"),
    path("<int:pk>/", views.PlanItemDetailView.as_view(), name="planitem-detail"),
]
