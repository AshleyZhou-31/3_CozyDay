"""A9 Stage 3 regression tests: cut-off answers must not reach the user.

Failure being guarded (see docs/ai_stage3_evaluation/README.md): the locked
generation step stops at max_new_tokens, so long answers (paper breakdown,
progress report) ended in the middle of a sentence and the page showed the
fragment as if it were a finished plan. Output validation now trims the
unfinished tail and shows a notice. No model is loaded here.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import rag_engine
from .test_rag_engine import _fake_engine

CUT_OFF = (
    "1. Choose a topic and write a one-sentence thesis.\n"
    "2. Find readings and take short notes on each source.\n"
    "3. Write an outline with a heading for every section.\n"
    "4. Draft the introduction and then the first body sec"
)
COMPLETE = "1. Choose a topic.\n2. Outline the paper.\n3. Draft and revise."


class FinalizeAnswerTests(SimpleTestCase):
    def test_complete_answer_is_unchanged_and_has_no_warning(self):
        self.assertEqual(rag_engine.finalize_answer(COMPLETE), (COMPLETE, None))

    def test_cut_off_list_drops_only_the_unfinished_item(self):
        text, warning = rag_engine.finalize_answer(CUT_OFF)
        self.assertTrue(text.endswith("for every section."))
        self.assertNotIn("first body sec", text)
        self.assertEqual(warning, rag_engine.TRUNCATION_WARNING)

    def test_cut_off_prose_drops_the_partial_sentence(self):
        text, warning = rag_engine.finalize_answer(
            "Start with the earliest deadline. Then estimate the remaining work for each and brea"
        )
        self.assertEqual(text, "Start with the earliest deadline.")
        self.assertIsNotNone(warning)

    def test_dangling_list_number_is_removed(self):
        text, _ = rag_engine.finalize_answer("1. Pick a topic. 2. Outline it. 3. Dra")
        self.assertEqual(text, "1. Pick a topic. 2. Outline it.")

    def test_no_finished_sentence_keeps_text_but_still_warns(self):
        text, warning = rag_engine.finalize_answer("Break the paper into smal")
        self.assertEqual(text, "Break the paper into smal")
        self.assertEqual(warning, rag_engine.TRUNCATION_WARNING)

    def test_empty_answer_stays_empty(self):
        self.assertEqual(rag_engine.finalize_answer("  "), ("", None))


@override_settings(AI_PLANNER_MAX_TIME_SECONDS=5)
class AnswerQueryValidationTests(SimpleTestCase):
    def run_query(self, answer_text):
        with patch.object(rag_engine, "get_engine", return_value=_fake_engine(answer_text=answer_text)):
            return rag_engine.answer_query("a planning question")

    def test_truncated_generation_is_trimmed_with_warning(self):
        result = self.run_query(CUT_OFF)
        self.assertTrue(result["answer"].endswith("for every section."))
        self.assertEqual(result["warning"], rag_engine.TRUNCATION_WARNING)

    @override_settings(AI_PLANNER_OUTPUT_VALIDATION=False)
    def test_switch_off_restores_baseline_behaviour_for_comparison(self):
        result = self.run_query(CUT_OFF)
        self.assertTrue(result["answer"].endswith("first body sec"))
        self.assertIsNone(result["warning"])

    def test_complete_generation_has_no_warning(self):
        self.assertIsNone(self.run_query(COMPLETE)["warning"])

    def test_stage_latencies_are_returned(self):
        latencies = self.run_query(COMPLETE)["stage_latencies"]
        self.assertEqual(set(latencies), {"embedding", "retrieval", "generation"})
        self.assertTrue(all(value >= 0 for value in latencies.values()))


class PageShowsValidationTests(TestCase):
    def test_page_shows_trimmed_answer_notice_and_stage_latencies(self):
        user = get_user_model().objects.create_user(username="stage3_user", password="test-password")
        self.client.force_login(user)
        trimmed, warning = rag_engine.finalize_answer(CUT_OFF)
        data = {
            "answer": trimmed,
            "retrieved_chunks": [{"id": "HYBRID_001", "text": "Split a paper.", "score": 0.7}],
            "latency_seconds": 1.5,
            "warning": warning,
            "stage_latencies": {"embedding": 0.1, "retrieval": 0.01, "generation": 1.2},
        }
        with patch("planner.views.generate_rag_plan", return_value=data):
            response = self.client.post(reverse("planner:ai-rag-planner"), {"query": "Break up my paper"})
        self.assertContains(response, "reached the length limit")
        self.assertContains(response, "generation 1.200s")
        self.assertNotContains(response, "first body sec")


@override_settings(AI_PLANNER_MAX_TIME_SECONDS=5)
class RelevanceGateTests(SimpleTestCase):
    """Failure: an out-of-scope or vague question retrieved unrelated chunks
    (best similarity 0.04 and 0.18) and the model answered anyway."""

    def run_query(self, query):
        # The fake encoder maps "a planning question" to the chunk vector
        # (similarity 1.0) and every other text to an orthogonal one (0.0).
        engine = _fake_engine(answer_text="Paris is the capital of France.")
        with patch.object(rag_engine, "get_engine", return_value=engine):
            return rag_engine.answer_query(query), engine

    def test_low_relevance_query_is_not_sent_to_the_model(self):
        with patch.object(rag_engine, "_generate_with_timeout") as generate:
            with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
                result = rag_engine.answer_query("capital of France")
        generate.assert_not_called()
        self.assertEqual(result["answer"], rag_engine.OUT_OF_SCOPE_ANSWER)
        self.assertIn("does not contain enough information", result["answer"])
        self.assertIn("No closely matching", result["warning"])
        self.assertEqual(result["stage_latencies"]["generation"], 0.0)
        self.assertEqual(len(result["retrieved_chunks"]), 1)

    def test_relevant_query_still_reaches_the_model(self):
        result, _ = self.run_query("a planning question")
        self.assertEqual(result["answer"], "Paris is the capital of France.")

    @override_settings(AI_PLANNER_MIN_RELEVANCE=0)
    def test_gate_can_be_disabled_for_baseline_comparison(self):
        result, _ = self.run_query("capital of France")
        self.assertEqual(result["answer"], "Paris is the capital of France.")

    @override_settings(AI_PLANNER_MIN_RELEVANCE=0.9)
    def test_threshold_is_configurable(self):
        engine = _fake_engine()
        engine["embedding_info"]["model"].vectors_by_text["partly related"] = (1.0, 1.0, 0.0)
        with patch.object(rag_engine, "get_engine", return_value=engine):
            result = rag_engine.answer_query("partly related")
        self.assertEqual(result["answer"], rag_engine.OUT_OF_SCOPE_ANSWER)

    def test_default_threshold_sits_between_measured_scores(self):
        self.assertGreater(rag_engine.DEFAULT_MIN_RELEVANCE, 0.183)
        self.assertLess(rag_engine.DEFAULT_MIN_RELEVANCE, 0.527)


class AnswerFormattingTests(TestCase):
    """Failure: the model's numbered list was shown as one run-on paragraph
    because the template ignored line breaks."""

    def post_answer(self, answer):
        user = get_user_model().objects.create_user(username="fmt_user", password="test-password")
        self.client.force_login(user)
        data = {"answer": answer, "retrieved_chunks": [], "latency_seconds": 0.1, "warning": None}
        with patch("planner.views.generate_rag_plan", return_value=data):
            return self.client.post(reverse("planner:ai-rag-planner"), {"query": "Break up my paper"})

    def test_line_breaks_in_the_answer_are_preserved(self):
        response = self.post_answer("Steps:\n\n1. Pick a topic.\n2. Write an outline.")
        self.assertContains(response, "<p>Steps:</p>")
        self.assertContains(response, "1. Pick a topic.<br>2. Write an outline.")

    def test_answer_html_is_still_escaped(self):
        response = self.post_answer("<script>alert(1)</script>\n\nDone.")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
