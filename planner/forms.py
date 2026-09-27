from django import forms

from .models import PlanItem


class PlanItemForm(forms.ModelForm):
    class Meta:
        model = PlanItem
        fields = [
            "title",
            "category",
            "item_type",
            "timing",
            "scheduled_date",
            "scheduled_time",
            "notes",
        ]
