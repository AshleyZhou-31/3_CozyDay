import json

from django.test import SimpleTestCase

from .plan_templates import (
    GENERAL,
    MONTHLY,
    THREE_MONTH,
    WEEKLY,
    detect_plan_type,
    format_structured_plan,
    get_template,
    parse_structured_plan,
)


class PlanTypeSelectionTests(SimpleTestCase):
    def test_selects_weekly_monthly_and_three_month_templates(self):
        self.assertEqual(detect_plan_type("Help me plan my study week"), WEEKLY)
        self.assertEqual(detect_plan_type("Make a plan for the next month"), MONTHLY)
        self.assertEqual(detect_plan_type("Build a 3-month research plan"), THREE_MONTH)

    def test_review_requested_timeframes(self):
        for query, expected in (("this week", WEEKLY), ("four weeks", MONTHLY),
                                ("next month", MONTHLY), ("12 weeks", THREE_MONTH)):
            with self.subTest(query=query):
                self.assertEqual(detect_plan_type(query), expected)

    def test_long_horizon_precedes_task_granularity(self):
        cases = (("four-week plan", MONTHLY), ("4 week plan", MONTHLY),
                 ("Weekly milestones for four weeks", MONTHLY),
                 ("Create a weekly schedule for next month", MONTHLY),
                 ("I have one month to prepare a research proposal", MONTHLY),
                 ("Weekly tasks for a twelve-week plan", THREE_MONTH),
                 ("Monthly milestones for three months", THREE_MONTH))
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(detect_plan_type(query), expected)

    def test_unknown_or_ambiguous_horizon_falls_back_to_general(self):
        self.assertEqual(detect_plan_type("Help me organize my thesis"), GENERAL)
        self.assertEqual(get_template("not-a-template"), get_template(GENERAL))

    def test_three_month_detection_precedes_month_detection(self):
        self.assertEqual(detect_plan_type("Plan the next three months"), THREE_MONTH)


class StructuredPlanValidationTests(SimpleTestCase):
    def setUp(self):
        self.payload = {
            "goal": "Prepare for the exam",
            "time_period": "Four weeks",
            "priorities": ["Review core topics"],
            "tasks_or_phases": ["Week 1: identify gaps"],
            "deadlines": [],
            "recommended_next_steps": ["List the topics"],
        }

    def test_parses_valid_json_and_json_markdown_fence(self):
        raw = json.dumps(self.payload)
        self.assertEqual(parse_structured_plan(raw), self.payload)
        self.assertEqual(parse_structured_plan(f"```json\n{raw}\n```"), self.payload)

    def test_rejects_invalid_json_missing_fields_and_wrong_field_types(self):
        for raw in ("not json", "{}", json.dumps({**self.payload, "priorities": "first"})):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_structured_plan(raw)

    def test_formats_all_required_fields_for_the_existing_result_page(self):
        rendered = format_structured_plan(self.payload)
        for field in ("Goal", "Time period", "Priorities", "Tasks or phases", "Deadlines", "Recommended next steps"):
            self.assertIn(field, rendered)
        self.assertIn("- None specified", rendered)
