"""The Stage 3 evaluation command, run against a fake engine (no models)."""
import csv
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from . import rag_engine
from .test_rag_engine import _fake_engine

CUT_OFF = "1. Choose a topic and thesis.\n2. Find readings.\n3. Draft the intro and the first body sec"


class RagEvaluateCommandTests(TestCase):
    def setUp(self):
        rag_engine.clear_engine_cache()
        self.addCleanup(rag_engine.clear_engine_cache)
        chunks = [{"chunk_id": "HYBRID_001", "text": "Split a paper into milestones.",
                   "source_ids": ["P002", "P001"]}]
        self.engine = _fake_engine(answer_text=CUT_OFF, chunks=chunks)
        self.engine["embedding_info"]["model"].default = (1.0, 0.0, 0.0)

    def run_command(self, out, *extra):
        with patch.object(rag_engine, "get_engine", return_value=self.engine):
            call_command("rag_evaluate", "--out", str(out), *extra, stdout=StringIO())
        with open(out, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_before_after_rows_for_the_same_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self.run_command(Path(tmp) / "runs.csv", "--cases", "Q1")
        by_variant = {r["variant"]: r for r in rows}
        self.assertEqual(set(by_variant), {"baseline", "improved"})
        self.assertEqual(by_variant["baseline"]["query"], by_variant["improved"]["query"])
        self.assertEqual(by_variant["baseline"]["ends_cleanly"], "False")
        self.assertEqual(by_variant["improved"]["status"], "validation_error")
        self.assertIn("could not format the plan correctly", by_variant["improved"]["error_message"])
        self.assertEqual(by_variant["baseline"]["warning"], "")

    def test_improved_variant_records_a_valid_structured_plan(self):
        valid = '{"goal":"Plan the paper","time_period":"Not specified","priorities":["Choose a topic"],"tasks_or_phases":["Outline the paper"],"deadlines":[],"recommended_next_steps":["Start an outline"]}'
        self.engine["generation_info"]["tokenizer"].text = valid
        with tempfile.TemporaryDirectory() as tmp:
            rows = self.run_command(Path(tmp) / "runs.csv", "--cases", "Q1", "--variants", "improved")
        self.assertEqual(rows[0]["status"], "ok")
        self.assertIn("Goal: Plan the paper", rows[0]["answer"])
        self.assertEqual(rows[0]["source_paragraph_ids"], "P002 | P001")

    def test_resumes_without_duplicating_rows_and_cleans_up_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "runs.csv"
            self.run_command(out, "--cases", "Q1")
            rows = self.run_command(out, "--cases", "Q1")
        self.assertEqual(len(rows), 2)
        self.assertFalse(get_user_model().objects.filter(username="rag_eval_user").exists())

    def test_vague_input_is_reported_with_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self.run_command(Path(tmp) / "runs.csv", "--cases", "X2", "--variants", "improved")
        self.assertEqual(rows[0]["case_id"], "X2")
        self.assertIn(rows[0]["status"], {"ok", "validation_error"})
