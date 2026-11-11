from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.Model):
    """
    Represents a user-created label such as School, Personal, or Wellness.
    It exists to organize CozyDay planning items without duplicating category names.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_category_per_user",
            )
        ]

    def __str__(self):
        return self.name


class PlanItem(models.Model):
    """
    Represents a task or event that a user wants to organize in CozyDay.
    It exists to power the Today, This Week, Later, and Whenever planning views.
    """

    class ItemType(models.TextChoices):
        TASK = "TASK", "Task"
        EVENT = "EVENT", "Event"

    class Timing(models.TextChoices):
        TODAY = "TODAY", "Today"
        THIS_WEEK = "THIS_WEEK", "This week"
        PICK_DATE = "PICK_DATE", "Pick a date"
        WHENEVER = "WHENEVER", "Whenever"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="plan_items",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_items",
    )
    title = models.CharField(max_length=150)
    item_type = models.CharField(
        max_length=10,
        choices=ItemType.choices,
        default=ItemType.TASK,
    )
    timing = models.CharField(
        max_length=20,
        choices=Timing.choices,
        default=Timing.TODAY,
    )
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "is_completed",
            "scheduled_date",
            "scheduled_time",
            "title",
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Return the canonical detail URL for this planning item."""
        return reverse("planner:planitem-detail", kwargs={"pk": self.pk})


class DailyCheckIn(models.Model):
    """
    Represents a user's optional mood and energy check-in for one calendar day.
    It exists to support daily awareness and recorded-day history without streak pressure.
    """

    class Mood(models.TextChoices):
        GOOD = "GOOD", "Good"
        OKAY = "OKAY", "Okay"
        LOW = "LOW", "Low"

    class Energy(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_check_ins",
    )
    date = models.DateField()
    mood = models.CharField(
        max_length=10,
        choices=Mood.choices,
        blank=True,
    )
    energy = models.CharField(
        max_length=10,
        choices=Energy.choices,
        blank=True,
    )
    note = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="unique_daily_check_in_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.date}"


class LifeEntry(models.Model):
    """
    Represents a note, idea, or meaningful everyday moment saved by a user.
    It exists to support Quick Capture and the My Life history in CozyDay.
    """

    class EntryType(models.TextChoices):
        NOTE = "NOTE", "Note or idea"
        MOMENT = "MOMENT", "Little moment"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="life_entries",
    )
    entry_type = models.CharField(
        max_length=10,
        choices=EntryType.choices,
    )
    content = models.TextField()
    tag = models.CharField(max_length=50, blank=True)
    entry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.content[:40]}"


class WeeklyReflection(models.Model):
    """
    Represents a user's editable reflection for one week.
    It exists to store personal reflections separately from automatically summarized activity.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_reflections",
    )
    week_start = models.DateField()
    reflection = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "week_start"],
                name="unique_weekly_reflection_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - week of {self.week_start}"


class AIPerformanceEvent(models.Model):
    """Privacy-minimal performance record for one RAG planner submission.

    Deliberately excludes prompt text, response text, user IDs, and retrieved
    content. This lets staff review aggregate reliability without retaining
    personal planning details.
    """

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Successful answer"
        ABSTENTION = "abstention", "Relevance abstention"
        ERROR = "error", "Error or invalid submission"

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    endpoint = models.CharField(max_length=40, default="rag_planner")
    outcome = models.CharField(max_length=12, choices=Outcome.choices, db_index=True)
    total_latency_ms = models.PositiveIntegerField()
    embedding_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    retrieval_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    generation_latency_ms = models.PositiveIntegerField(null=True, blank=True)
    validation_latency_ms = models.PositiveIntegerField(default=0)
    max_similarity_score = models.FloatField(null=True, blank=True)
    retrieved_count = models.PositiveSmallIntegerField(default=0)
    query_length_chars = models.PositiveSmallIntegerField(null=True, blank=True)
    query_category = models.CharField(max_length=50, null=True, blank=True)
    input_tokens_estimate = models.PositiveIntegerField(null=True, blank=True)
    output_tokens_estimate = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True
    )
    is_simulated = models.BooleanField(default=False, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at", "outcome"], name="aiperf_created_outcome_idx")]

    def __str__(self):
        return f"{self.get_outcome_display()} at {self.created_at:%Y-%m-%d %H:%M}"

