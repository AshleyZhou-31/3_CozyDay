from django.contrib import admin
from django.urls import path, include

from planner import views as planner_views

urlpatterns = [
    path('', planner_views.home, name='home'),
    path('admin/', admin.site.urls),
    path('planitems/', include('planner.urls')),
]
