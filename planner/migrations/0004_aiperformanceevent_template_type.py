from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0003_aiperformanceevent_estimated_cost_usd_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiperformanceevent",
            name="template_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("general", "General"),
                    ("weekly", "Weekly plan"),
                    ("monthly", "Monthly plan"),
                    ("three_month", "Three-month plan"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
