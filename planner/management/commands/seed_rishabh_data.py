from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from planner.models import (
    Category,
    PlanItem,
    DailyCheckIn,
    LifeEntry,
    WeeklyReflection,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds demo data and tests the three uniqueness constraints for Part 4."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="rishabh_demo",
            defaults={"email": "rishabh_demo@example.com"},
        )
        if created:
            user.set_password("demopassword123")
            user.save()
        self.stdout.write(self.style.SUCCESS(f"Using demo user: {user.username} (created={created})"))

        # ---------- Categories ----------
        category_data = [
            ("School", "#4A90D9"),
            ("Personal", "#7ED6A5"),
            ("Wellness", "#F2C94C"),
            ("Social", "#EB5757"),
            ("Errands", "#9B51E0"),
        ]
        categories = {}
        for name, color in category_data:
            cat, _ = Category.objects.get_or_create(
                user=user, name=name, defaults={"color": color}
            )
            categories[name] = cat

        # ---------- PlanItems ----------
        today = date.today()
        plan_items = [
            dict(title="Finish INFO 490 Part 4 write-up", category=categories["School"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.TODAY,
                 scheduled_date=today, scheduled_time=time(18, 0), notes="Seed data + constraint tests"),
            dict(title="Submit assignment on Canvas", category=categories["School"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.THIS_WEEK,
                 scheduled_date=today + timedelta(days=2)),
            dict(title="Study group meeting", category=categories["School"],
                 item_type=PlanItem.ItemType.EVENT, timing=PlanItem.Timing.PICK_DATE,
                 scheduled_date=today + timedelta(days=3), scheduled_time=time(15, 30)),
            dict(title="Doctor's appointment", category=categories["Wellness"],
                 item_type=PlanItem.ItemType.EVENT, timing=PlanItem.Timing.PICK_DATE,
                 scheduled_date=today + timedelta(days=5), scheduled_time=time(10, 0)),
            dict(title="Morning run", category=categories["Wellness"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.TODAY,
                 scheduled_date=today, is_completed=True),
            dict(title="Grocery shopping", category=categories["Errands"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.THIS_WEEK,
                 scheduled_date=today + timedelta(days=1)),
            dict(title="Pick up dry cleaning", category=categories["Errands"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.WHENEVER),
            dict(title="Call parents", category=categories["Personal"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.WHENEVER),
            dict(title="Birthday dinner with friends", category=categories["Social"],
                 item_type=PlanItem.ItemType.EVENT, timing=PlanItem.Timing.PICK_DATE,
                 scheduled_date=today + timedelta(days=7), scheduled_time=time(19, 30)),
            dict(title="Plan weekend trip", category=categories["Personal"],
                 item_type=PlanItem.ItemType.TASK, timing=PlanItem.Timing.THIS_WEEK,
                 scheduled_date=today + timedelta(days=4)),
        ]
        for item in plan_items:
            PlanItem.objects.get_or_create(user=user, title=item["title"], defaults=item)

        # ---------- DailyCheckIns ----------
        # Note: dates are computed relative to today(), so running this command again on a
        # later day will add new check-ins for the new dates rather than matching old ones —
        # existing rows for past dates are left untouched. No reset/delete logic by design.
        checkin_data = [
            (today, DailyCheckIn.Mood.GOOD, DailyCheckIn.Energy.HIGH, "Productive day, finished two tasks."),
            (today - timedelta(days=1), DailyCheckIn.Mood.OKAY, DailyCheckIn.Energy.MEDIUM, "Bit tired but got through classes."),
            (today - timedelta(days=2), DailyCheckIn.Mood.LOW, DailyCheckIn.Energy.LOW, "Rough day, exam stress."),
            (today - timedelta(days=3), DailyCheckIn.Mood.GOOD, DailyCheckIn.Energy.MEDIUM, "Good workout this morning."),
            (today - timedelta(days=4), DailyCheckIn.Mood.OKAY, DailyCheckIn.Energy.HIGH, "Busy but manageable."),
            (today - timedelta(days=5), DailyCheckIn.Mood.GOOD, DailyCheckIn.Energy.HIGH, "Relaxing weekend start."),
            (today - timedelta(days=6), DailyCheckIn.Mood.LOW, DailyCheckIn.Energy.MEDIUM, "Overslept, felt behind."),
        ]
        for d, mood, energy, note in checkin_data:
            DailyCheckIn.objects.get_or_create(
                user=user, date=d, defaults={"mood": mood, "energy": energy, "note": note}
            )

        # ---------- LifeEntries ----------
        life_entry_data = [
            (LifeEntry.EntryType.NOTE, "Idea: add a weekly mood trend chart to the dashboard.", "idea", today),
            (LifeEntry.EntryType.MOMENT, "Had coffee with an old friend, first time in months.", "social", today - timedelta(days=1)),
            (LifeEntry.EntryType.NOTE, "Remember to email professor about the extension.", "school", today - timedelta(days=2)),
            (LifeEntry.EntryType.MOMENT, "Watched the sunset from the quad, nice reset.", "wellness", today - timedelta(days=3)),
            (LifeEntry.EntryType.NOTE, "Idea: low-capacity mode for the dashboard on overloaded days.", "idea", today - timedelta(days=4)),
            (LifeEntry.EntryType.MOMENT, "Cooked a new recipe, turned out better than expected.", "personal", today - timedelta(days=5)),
        ]
        for entry_type, content, tag, entry_date in life_entry_data:
            LifeEntry.objects.get_or_create(
                user=user, content=content,
                defaults={"entry_type": entry_type, "tag": tag, "entry_date": entry_date},
            )

        # ---------- WeeklyReflections ----------
        def monday_of(d):
            return d - timedelta(days=d.weekday())

        this_monday = monday_of(today)
        reflection_data = [
            (this_monday, "This week felt balanced — kept up with school while still making time to rest."),
            (this_monday - timedelta(days=7), "Overloaded week, too many deadlines stacked on the same days."),
            (this_monday - timedelta(days=14), "Slow week, used the extra time to plan ahead for midterms."),
        ]
        for week_start, reflection in reflection_data:
            WeeklyReflection.objects.get_or_create(
                user=user, week_start=week_start, defaults={"reflection": reflection}
            )

        # ---------- Actual database counts (not input-list lengths) ----------
        self.stdout.write(self.style.WARNING("\n--- Database counts for rishabh_demo ---"))
        self.stdout.write(f"Categories: {Category.objects.filter(user=user).count()}")
        self.stdout.write(f"PlanItems: {PlanItem.objects.filter(user=user).count()}")
        self.stdout.write(f"DailyCheckIns: {DailyCheckIn.objects.filter(user=user).count()}")
        self.stdout.write(f"LifeEntries: {LifeEntry.objects.filter(user=user).count()}")
        self.stdout.write(f"WeeklyReflections: {WeeklyReflection.objects.filter(user=user).count()}")

        # ---------- Uniqueness constraint tests ----------
        self.stdout.write(self.style.WARNING("\n--- Running uniqueness constraint tests ---"))
        failures = []
        self._test_constraint(
            "Category(user, name)",
            lambda: Category.objects.create(user=user, name="School", color="#000000"),
            failures,
        )
        self._test_constraint(
            "DailyCheckIn(user, date)",
            lambda: DailyCheckIn.objects.create(user=user, date=today, mood=DailyCheckIn.Mood.OKAY),
            failures,
        )
        self._test_constraint(
            "WeeklyReflection(user, week_start)",
            lambda: WeeklyReflection.objects.create(user=user, week_start=this_monday, reflection="duplicate"),
            failures,
        )

        if failures:
            raise CommandError(
                "Uniqueness constraint check(s) failed: " + ", ".join(failures)
            )

    def _test_constraint(self, label, attempt_fn, failures):
        try:
            with transaction.atomic():
                attempt_fn()
                # Reaching this line means the duplicate insert did NOT raise
                # IntegrityError, which is the failure case. Force this block to
                # roll back so the bad row is never actually committed, then
                # report the failure once we're safely outside the transaction.
                transaction.set_rollback(True)
            self.stdout.write(self.style.ERROR(
                f"[FAIL] {label}: Expected IntegrityError on duplicate, but the save succeeded (row rolled back, not persisted)."
            ))
            failures.append(label)
        except IntegrityError:
            self.stdout.write(self.style.SUCCESS(
                f"[PASS] {label}: Expected IntegrityError, got IntegrityError."
            ))