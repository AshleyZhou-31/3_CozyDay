from django.contrib import admin
from django.urls import path, include
from django.urls import include

from planner import views as planner_views
from django.contrib.auth import views as auth_views





urlpatterns = [
    path('', planner_views.home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('planitems/', include('planner.urls')),

    path('api/summary/', planner_views.api_summary, name='api-summary'),
    path('charts/category-summary/', planner_views.chart_category_summary, name='chart-category-summary'),
    path('charts/activity-over-time/', planner_views.chart_activity_over_time, name='chart-activity-over-time'),
    path('vega-lite/chart1.png', planner_views.vega_chart1_png, name='vega-chart1-png'),
    path('vega-lite/chart2.png', planner_views.vega_chart2_png, name='vega-chart2-png'),

    path(
        'login/',
        auth_views.LoginView.as_view(template_name='planner/login.html'),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
    path('signup/', planner_views.signup, name='signup'),
]