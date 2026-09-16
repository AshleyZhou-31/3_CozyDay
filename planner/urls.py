from django.urls import path

from . import views

urlpatterns = [
    path("manual/", views.planitem_list_manual, name="planitem-manual"),
    path("render/", views.planitem_list_render, name="planitem-render"),
    path("cbv-base/", views.PlanItemListBaseView.as_view(), name="planitem-cbv-base"),
    path("cbv-generic/", views.PlanItemListView.as_view(), name="planitem-cbv-generic"),
]