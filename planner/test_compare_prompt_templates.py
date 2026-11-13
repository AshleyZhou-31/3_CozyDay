"""Mocked command tests; fixtures are not model evaluation evidence."""
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class ComparePromptTemplatesCommandTests(SimpleTestCase):
    @patch("planner.management.commands.compare_prompt_templates.answer_query")
    def test_saves_all_variants_and_checkpoints_before_next_call(self, answer):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "results.json"
            calls = []
            def generate(query, **kwargs):
                if calls:
                    self.assertEqual(len(json.loads(path.read_text())), len(calls))
                calls.append(kwargs)
                return {"structured_plan": {"goal": "Fixture"}, "warning": None}
            answer.side_effect = generate
            stdout = StringIO()
            call_command("compare_prompt_templates", output=str(path),
                         max_time_seconds=300, stdout=stdout, stderr=StringIO())
            rows = json.loads(path.read_text())
            self.assertEqual(rows, json.loads(stdout.getvalue()))
            self.assertEqual([r["variant"] for r in rows],
                             ["general", "weekly", "general", "monthly", "general", "three_month"])
            self.assertTrue(all(r["status"] == "success" for r in rows))
            self.assertEqual(len(calls), 6)
            self.assertTrue(all(c["max_time_seconds"] == 300 for c in calls))

    @patch("planner.management.commands.compare_prompt_templates.answer_query")
    def test_records_errors_and_abstentions_without_exception_text(self, answer):
        answer.side_effect = [RuntimeError("private text")] + [
            {"structured_plan": None, "warning": "No relevant guidance"}
        ] * 5
        with TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            with self.assertRaises(CommandError):
                call_command("compare_prompt_templates", output=str(path),
                             stdout=StringIO(), stderr=StringIO())
            text = path.read_text()
            rows = json.loads(text)
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["status"], "error")
            self.assertEqual(rows[1]["status"], "no_plan")
            self.assertNotIn("private text", text)

    @patch("planner.management.commands.compare_prompt_templates.answer_query")
    def test_rejects_invalid_timeout(self, answer):
        with self.assertRaises(CommandError):
            call_command("compare_prompt_templates", max_time_seconds=0)
        answer.assert_not_called()
