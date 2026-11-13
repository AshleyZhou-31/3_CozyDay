from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import rag_engine
from .ai_cost import (
    build_usage,
    count_tokens,
    estimate_cost_usd,
    model_name_label,
    serving_backend_label,
)
from .models import AIPerformanceEvent
from .test_rag_engine import _fake_engine


class CountTokensTests(SimpleTestCase):
    def test_empty_and_non_string_are_zero(self):
        self.assertEqual(count_tokens(""), 0)
        self.assertEqual(count_tokens(None), 0)
        self.assertEqual(count_tokens(123), 0)

    def test_fallback_is_one_token_per_four_characters_rounded_up(self):
        self.assertEqual(count_tokens("abcd"), 1)
        self.assertEqual(count_tokens("abcde"), 2)

    def test_real_tokenizer_is_used_when_it_returns_a_list(self):
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]
        self.assertEqual(count_tokens("hello world", tokenizer), 3)

    def test_unusable_tokenizer_falls_back_without_raising(self):
        broken = MagicMock()
        broken.encode.side_effect = RuntimeError("boom")
        self.assertEqual(count_tokens("abcdefgh", broken), 2)
        # A mock returning a non-list (len() of a MagicMock is 0) must not give 0.
        self.assertEqual(count_tokens("abcdefgh", MagicMock()), 2)


@override_settings(AI_COST_INPUT_USD_PER_1K=0.001, AI_COST_OUTPUT_USD_PER_1K=0.002)
class CostEstimateTests(SimpleTestCase):
    def test_cost_is_tokens_times_assumed_price_per_thousand(self):
        # 2,000 input x 0.001/1k + 500 output x 0.002/1k = 0.002 + 0.001
        self.assertEqual(estimate_cost_usd(2000, 500), Decimal("0.00300000"))

    def test_zero_tokens_cost_zero(self):
        self.assertEqual(estimate_cost_usd(0, 0), Decimal("0E-8"))

    def test_negative_or_missing_tokens_are_treated_as_zero(self):
        self.assertEqual(estimate_cost_usd(-5, None), Decimal("0E-8"))

    @override_settings(AI_COST_INPUT_USD_PER_1K="not-a-number")
    def test_bad_price_setting_falls_back_to_default(self):
        self.assertGreaterEqual(estimate_cost_usd(1000, 0), Decimal("0"))


class BuildUsageTests(SimpleTestCase):
    @override_settings(AI_SERVING_BACKEND="transformers-local")
    def test_generated_request_counts_prompt_and_answer(self):
        usage = build_usage(
            generated=True,
            system_instruction="a" * 40,
            chunks=[{"text": "b" * 40}],
            query="c" * 40,
            answer="d" * 80,
            generation_info={"model_name": "Qwen/Qwen2.5-3B-Instruct"},
        )
        self.assertGreater(usage["input_tokens"], 30)
        self.assertEqual(usage["output_tokens"], 20)
        self.assertGreater(usage["estimated_cost_usd"], Decimal("0"))
        self.assertEqual(usage["model_name"], "Qwen/Qwen2.5-3B-Instruct")
        self.assertEqual(usage["serving_backend"], "transformers-local")

    def test_abstention_has_zero_tokens_and_zero_cost(self):
        usage = build_usage(
            generated=False, system_instruction=None, chunks=None, query=None,
            answer=None, generation_info={"model_name": "m"},
        )
        self.assertEqual(usage["input_tokens"], 0)
        self.assertEqual(usage["output_tokens"], 0)
        self.assertEqual(usage["estimated_cost_usd"], Decimal("0E-8"))

    def test_model_name_falls_back_to_setting_for_non_dict_info(self):
        with override_settings(AI_PLANNER_MODEL_ID="fallback-model"):
            self.assertEqual(model_name_label(MagicMock()), "fallback-model")

    def test_blank_backend_setting_uses_default(self):
        with override_settings(AI_SERVING_BACKEND="  "):
            self.assertEqual(serving_backend_label(), "transformers-local")

    def test_internal_failure_returns_none_instead_of_raising(self):
        with patch("planner.ai_cost.count_tokens", side_effect=RuntimeError("boom")):
            usage = build_usage(
                generated=True, system_instruction="s", chunks=[], query="q",
                answer="a", generation_info=None,
            )
        self.assertIsNone(usage)


@override_settings(AI_PLANNER_MAX_TIME_SECONDS=5)
class EngineUsageTests(SimpleTestCase):
    """The engine result carries usage and never carries the prompt text."""

    def setUp(self):
        rag_engine.clear_engine_cache()
        self.addCleanup(rag_engine.clear_engine_cache)

    def test_successful_answer_reports_tokens_cost_model_and_backend(self):
        with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
            result = rag_engine.answer_query("a planning question")
        usage = result["usage"]
        self.assertGreater(usage["input_tokens"], 0)
        self.assertGreater(usage["output_tokens"], 0)
        self.assertGreater(usage["estimated_cost_usd"], Decimal("0"))
        self.assertEqual(usage["model_name"], "Qwen/Qwen2.5-3B-Instruct")
        self.assertEqual(usage["serving_backend"], "transformers-local")
        self.assertNotIn("a planning question", repr(usage))

    def test_relevance_abstention_has_zero_tokens_and_cost(self):
        with patch.object(rag_engine, "_generate_with_timeout") as generate:
            with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
                result = rag_engine.answer_query("capital of France")
        generate.assert_not_called()
        self.assertEqual(result["outcome"], "abstention")
        self.assertEqual(result["usage"]["input_tokens"], 0)
        self.assertEqual(result["usage"]["output_tokens"], 0)
        self.assertEqual(result["usage"]["estimated_cost_usd"], Decimal("0E-8"))

    def test_service_adapter_passes_usage_through(self):
        from .rag_planner import generate_rag_plan

        with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
            result = generate_rag_plan("a planning question")
        self.assertIn("usage", result)
        self.assertGreater(result["usage"]["input_tokens"], 0)


class ViewRecordsUsageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cost-test", password="test-password-123"
        )
        self.client.force_login(self.user)

    def _result(self, usage):
        result = {
            "answer": "Break the task into steps.",
            "structured_plan": {
                "goal": "Break the task into steps.", "time_period": "Not specified",
                "priorities": [], "tasks_or_phases": ["Break into steps"],
                "deadlines": [], "recommended_next_steps": ["Choose a first step"],
            },
            "template_type": "general",
            "outcome": "success",
            "retrieved_chunks": [{"id": "CHUNK_1", "text": "guidance", "score": .72}],
            "latency_seconds": .12,
            "stage_latencies": {"embedding": .02, "retrieval": .01, "generation": .07},
            "warning": None,
        }
        if usage is not None:
            result["usage"] = usage
        return result

    @patch("planner.views.generate_rag_plan")
    def test_usage_is_stored_on_the_event_without_text(self, generate):
        generate.return_value = self._result({
            "input_tokens": 420, "output_tokens": 180,
            "estimated_cost_usd": Decimal("0.00015600"),
            "model_name": "Qwen/Qwen2.5-3B-Instruct",
            "serving_backend": "transformers-local",
        })
        self.client.post(reverse("planner:ai-rag-planner"), {"query": "SECRET PLAN TEXT here"})
        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, AIPerformanceEvent.Outcome.SUCCESS)
        self.assertEqual(event.input_tokens_estimate, 420)
        self.assertEqual(event.output_tokens_estimate, 180)
        self.assertEqual(event.estimated_cost_usd, Decimal("0.00015600"))
        self.assertEqual(event.model_name, "Qwen/Qwen2.5-3B-Instruct")
        self.assertEqual(event.serving_backend, "transformers-local")
        self.assertNotIn("SECRET PLAN TEXT", repr(event.__dict__))

    @patch("planner.views.generate_rag_plan")
    def test_missing_usage_leaves_cost_fields_empty(self, generate):
        generate.return_value = self._result(None)
        self.client.post(reverse("planner:ai-rag-planner"), {"query": "Break down my paper"})
        event = AIPerformanceEvent.objects.get()
        self.assertEqual(event.outcome, AIPerformanceEvent.Outcome.SUCCESS)
        self.assertIsNone(event.input_tokens_estimate)
        self.assertIsNone(event.estimated_cost_usd)
        self.assertEqual(event.model_name, "")
