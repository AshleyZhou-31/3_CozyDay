from django.contrib import admin

from .models import (
    Category,
    PlanItem,
    DailyCheckIn,
    LifeEntry,
    WeeklyReflection,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color")
    search_fields = ("name", "user__username")


@admin.register(PlanItem)
class PlanItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "category",
        "item_type",
        "timing",
        "scheduled_date",
        "is_completed",
    )
    list_filter = ("item_type", "timing", "is_completed", "category")
    search_fields = ("title", "notes", "user__username", "category__name")
    date_hierarchy = "scheduled_date"


@admin.register(DailyCheckIn)
class DailyCheckInAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "mood", "energy")
    list_filter = ("mood", "energy")
    search_fields = ("user__username", "note")
    date_hierarchy = "date"


@admin.register(LifeEntry)
class LifeEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "entry_type", "tag", "entry_date")
    list_filter = ("entry_type", "tag")
    search_fields = ("content", "tag", "user__username")
    date_hierarchy = "entry_date"


@admin.register(WeeklyReflection)
class WeeklyReflectionAdmin(admin.ModelAdmin):
    list_display = ("user", "week_start", "created_at", "updated_at")
    search_fields = ("user__username", "reflection")
    date_hierarchy = "week_start"