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
    path('api/plan-items/', views.plan_items_api, name='plan-items-api'),
    path("search/", views.planitem_search, name="planitem-search"),
    path("analytics/", views.analytics, name="analytics"),
    path("chart/category.png", views.category_chart_png, name="category-chart-png"),
    path("reports/", views.reports, name="planitem-reports"),
    path("api/export/csv/", views.export_plan_items_csv, name="planitem-export-csv"),
    path("api/export/json/", views.export_plan_items_json, name="planitem-export-json"),
]
