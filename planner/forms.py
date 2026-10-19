from django import forms
from django.conf import settings

from .ai_planner import AIInputError, clean_user_text
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


class AIPlannerForm(forms.Form):
    """Free-text request for the local AI planner."""

    request_text = forms.CharField(
        label="What do you need to plan?",
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text="Describe your tasks, fixed times and how long you have.",
    )
    include_plan_items = forms.BooleanField(
        label="Also include my open plan items",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["request_text"].widget.attrs["maxlength"] = getattr(
            settings, "AI_PLANNER_MAX_INPUT_CHARS", 600
        ) * 2  # browser hint only; the real limit is checked after cleaning

    def clean_request_text(self):
        try:
            return clean_user_text(self.cleaned_data["request_text"])
        except AIInputError as exc:
            raise forms.ValidationError(exc.user_message)
