from django import forms

from .models import Category, PlanItem


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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["category"].queryset = Category.objects.filter(user=user)
        else:
            self.fields["category"].queryset = Category.objects.none()