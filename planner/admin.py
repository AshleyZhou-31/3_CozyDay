from django.contrib import admin

from .models import (
    Category,
    PlanItem,
    DailyCheckIn,
    LifeEntry,
    WeeklyReflection,
)

admin.site.register(Category)
admin.site.register(PlanItem)
admin.site.register(DailyCheckIn)
admin.site.register(LifeEntry)
admin.site.register(WeeklyReflection)