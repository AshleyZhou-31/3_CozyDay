"""Tests for the local AI planner. No model is ever downloaded or loaded:
torch/transformers and generation are replaced with small fakes."""

import contextlib
import sys
import types
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import ai_planner
from .ai_planner import (
    AIGenerationError,
    AIInputError,
    AIOutputError,
    AIUnavailableError,
    PlannerResult,
    build_prompt,
    build_user_message,
    clean_user_text,
    generate_plan,
    parse_response,
)
from .models import PlanItem

GOOD_RESPONSE = (
    "Priority: Finish the report\n"
    "Schedule:\n"
    "1. Work on the report this morning.\n"
    "2. Buy groceries after lunch.\n"
    "Reason: The report is due tomorrow."
)


class CleanTextTests(SimpleTestCase):
    def test_collapses_whitespace_and_strips(self):
        self.assertEqual(clean_user_text("  finish   report\n\n today\t"), "finish report today")

    def test_removes_control_and_invisible_characters(self):
        self.assertEqual(clean_user_text("fin\x00ish​ report\x07"), "fin ish report")

    def test_empty_and_whitespace_only_are_rejected(self):
        for value in ["", "   \n\t ", None, "\x00\x01"]:
            with self.assertRaises(AIInputError):
                clean_user_text(value)

    @override_settings(AI_PLANNER_MAX_INPUT_CHARS=20)
    def test_too_long_is_rejected_not_truncated(self):
        with self.assertRaises(AIInputError) as ctx:
            clean_user_text("x" * 21)
        self.assertIn("under 20", ctx.exception.user_message)
        self.assertEqual(clean_user_text("x" * 20), "x" * 20)

    def test_user_message_appends_cleaned_limited_plan_items(self):
        titles = ["  Write   essay ", "", "Call mom"] + [f"Item {i}" for i in range(20)]
        with override_settings(AI_PLANNER_MAX_PLAN_ITEMS=3):
            message = build_user_message("Plan my day", titles)
        self.assertEqual(message, "Plan my day My open plan items: Write essay; Call mom; Item 0.")

    def test_user_message_without_items_is_just_the_request(self):
        self.assertEqual(build_user_message("  Plan   my day "), "Plan my day")


class FakeTokenizer:
    eos_token_id = 0
    chat_template = "fake-template"

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        self.messages = messages
        return "|".join(f"{m['role']}:{m['content']}" for m in messages)


class PromptTests(SimpleTestCase):
    def test_prompt_has_system_three_shots_and_user_message(self):
        tokenizer = FakeTokenizer()
        build_prompt(tokenizer, "My request")
        roles = [m["role"] for m in tokenizer.messages]
        self.assertEqual(roles, ["system"] + ["user", "assistant"] * 3 + ["user"])
        self.assertEqual(tokenizer.messages[0]["content"], ai_planner.SYSTEM_INSTRUCTION)
        self.assertEqual(tokenizer.messages[-1]["content"], "My request")

    def test_zero_shots(self):
        tokenizer = FakeTokenizer()
        build_prompt(tokenizer, "My request", n_shots=0)
        self.assertEqual([m["role"] for m in tokenizer.messages], ["system", "user"])


class NoSystemRoleTokenizer(FakeTokenizer):
    """Behaves like Gemma's template: rejects the system role."""

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        if any(m["role"] == "system" for m in messages):
            raise ValueError("System role not supported")
        return super().apply_chat_template(messages, tokenize, add_generation_prompt)


class BrokenTemplateTokenizer(FakeTokenizer):
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        raise ValueError("template error")


class NoTemplateTokenizer:
    chat_template = None


class PromptFallbackTests(SimpleTestCase):
    def test_system_role_rejected_folds_instruction_into_first_user_turn(self):
        tokenizer = NoSystemRoleTokenizer()
        prompt = build_prompt(tokenizer, "My request")
        messages = tokenizer.messages
        self.assertNotIn("system", [m["role"] for m in messages])
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"] * 3 + ["user"])
        self.assertTrue(
            messages[0]["content"].startswith(ai_planner.SYSTEM_INSTRUCTION)
        )
        self.assertIn(ai_planner.SHOT_EXAMPLES[0]["input"], messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "My request")
        self.assertIn("My request", prompt)

    def test_zero_shots_without_system_role_folds_into_the_request(self):
        tokenizer = NoSystemRoleTokenizer()
        build_prompt(tokenizer, "My request", n_shots=0)
        self.assertEqual(
            tokenizer.messages,
            [{"role": "user", "content": f"{ai_planner.SYSTEM_INSTRUCTION}\n\nMy request"}],
        )

    def test_broken_template_falls_back_to_plain_text(self):
        prompt = build_prompt(BrokenTemplateTokenizer(), "My request")
        self.assertIn(ai_planner.SYSTEM_INSTRUCTION, prompt)
        self.assertIn("User request:\nMy request", prompt)
        self.assertTrue(prompt.endswith("Assistant response:\n"))

    def test_tokenizer_without_chat_template_uses_plain_text(self):
        prompt = build_prompt(NoTemplateTokenizer(), "My request", n_shots=1)
        self.assertIn(ai_planner.SYSTEM_INSTRUCTION, prompt)
        self.assertIn(ai_planner.SHOT_EXAMPLES[0]["response"], prompt)
        self.assertIn("User request:\nMy request", prompt)


class ParseResponseTests(SimpleTestCase):
    def test_parses_well_formed_response(self):
        result = parse_response(GOOD_RESPONSE)
        self.assertEqual(result.priority, "Finish the report")
        self.assertEqual(result.schedule, ["Work on the report this morning.", "Buy groceries after lunch."])
        self.assertEqual(result.reason, "The report is due tomorrow.")
        self.assertTrue(result.complete)

    def test_parses_markdown_bold_headings_and_bullets(self):
        text = "**Priority:** Study\n**Schedule:**\n- 9 AM: **Study**\n* 10 AM: Break\n**Reason:** Focus first."
        result = parse_response(text)
        self.assertEqual(result.priority, "Study")
        self.assertEqual(result.schedule, ["9 AM: Study", "10 AM: Break"])
        self.assertEqual(result.reason, "Focus first.")

    def test_schedule_on_same_line_as_heading(self):
        result = parse_response("Priority: A\nSchedule: 1. Do A\nReason: Because.")
        self.assertEqual(result.schedule, ["Do A"])

    def test_missing_reason_is_tolerated_but_incomplete(self):
        result = parse_response("Priority: A\nSchedule:\n1. Do A", truncated=True)
        self.assertEqual(result.reason, "")
        self.assertFalse(result.complete)
        self.assertTrue(result.truncated)

    def test_empty_output_raises(self):
        for value in ["", "   \n", None]:
            with self.assertRaises(AIOutputError):
                parse_response(value)

    def test_unstructured_output_raises(self):
        with self.assertRaises(AIOutputError):
            parse_response("I think you should clean your room first.")

    def test_priority_without_schedule_raises(self):
        with self.assertRaises(AIOutputError):
            parse_response("Priority: A\nReason: Because.")


class FakeIds:
    shape = (1, 5)

    def to(self, device):
        return self


class FakeModel:
    device = "cpu"

    def __init__(self, text=GOOD_RESPONSE, new_tokens=40, error=None):
        self.kwargs = None
        self.error = error
        self._tokens = new_tokens

    def generate(self, **kwargs):
        if self.error:
            raise self.error
        self.kwargs = kwargs
        return [list(range(5 + self._tokens))]


class FakeGenTokenizer(FakeTokenizer):
    def __init__(self, text=GOOD_RESPONSE):
        self.text = text

    def __call__(self, prompt, return_tensors):
        return {"input_ids": FakeIds()}

    def decode(self, tokens, skip_special_tokens):
        return self.text


def fake_torch():
    module = types.ModuleType("torch")
    module.inference_mode = contextlib.nullcontext
    return module


@override_settings(AI_PLANNER_MAX_NEW_TOKENS=256, AI_PLANNER_MAX_TIME_SECONDS=120)
class GeneratePlanTests(SimpleTestCase):
    def run_generate(self, tokenizer, model, **kwargs):
        with patch.dict(sys.modules, {"torch": fake_torch()}), patch(
            "planner.ai_planner.get_model", return_value=(tokenizer, model)
        ):
            return generate_plan("Plan my day", **kwargs)

    def test_returns_parsed_result_and_passes_generation_limits(self):
        model = FakeModel()
        result = self.run_generate(FakeGenTokenizer(), model)
        self.assertEqual(result.priority, "Finish the report")
        self.assertFalse(result.truncated)
        self.assertEqual(model.kwargs["max_new_tokens"], 256)
        self.assertEqual(model.kwargs["max_time"], 120)
        self.assertFalse(model.kwargs["do_sample"])

    def test_hitting_token_limit_marks_result_truncated(self):
        result = self.run_generate(FakeGenTokenizer("Priority: A\nSchedule:\n1. Do A"), FakeModel(new_tokens=256))
        self.assertTrue(result.truncated)
        self.assertFalse(result.complete)

    def test_empty_model_output_raises_output_error(self):
        with self.assertRaises(AIOutputError):
            self.run_generate(FakeGenTokenizer(""), FakeModel())

    def test_malformed_model_output_raises_output_error(self):
        with self.assertRaises(AIOutputError):
            self.run_generate(FakeGenTokenizer("no headings here"), FakeModel())

    def test_model_exception_becomes_generation_error(self):
        with self.assertLogs("planner.ai_planner", "ERROR"), self.assertRaises(AIGenerationError):
            self.run_generate(FakeGenTokenizer(), FakeModel(error=RuntimeError("out of memory")))

    def test_bad_input_is_rejected_before_loading_the_model(self):
        with patch("planner.ai_planner.get_model") as get_model:
            with self.assertRaises(AIInputError):
                generate_plan("   ")
        get_model.assert_not_called()


class ModelLoadingTests(SimpleTestCase):
    def setUp(self):
        ai_planner.clear_model_cache()
        self.addCleanup(ai_planner.clear_model_cache)

    def test_missing_packages_raise_unavailable(self):
        with patch.dict(sys.modules, {"torch": None}), self.assertLogs("planner.ai_planner", "WARNING"):
            with self.assertRaises(AIUnavailableError):
                ai_planner.get_model("some/model")

    def test_load_failure_raises_unavailable_and_is_not_cached(self):
        torch_module = fake_torch()
        torch_module.cuda = types.SimpleNamespace(is_available=lambda: False)
        torch_module.backends = types.SimpleNamespace()
        torch_module.bfloat16 = "bf16"
        transformers_module = types.ModuleType("transformers")

        class Loader:
            calls = 0

            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                cls.calls += 1
                raise OSError("network down")

        transformers_module.AutoTokenizer = Loader
        transformers_module.AutoModelForCausalLM = Loader
        with patch.dict(sys.modules, {"torch": torch_module, "transformers": transformers_module}), \
                self.assertLogs("planner.ai_planner", "ERROR"):
            with self.assertRaises(AIUnavailableError):
                ai_planner.get_model("some/model")
            with self.assertRaises(AIUnavailableError):
                ai_planner.get_model("some/model")
        self.assertEqual(Loader.calls, 2)  # failure is retried, not cached

    def test_successful_load_is_cached(self):
        torch_module = fake_torch()
        torch_module.cuda = types.SimpleNamespace(is_available=lambda: False)
        torch_module.backends = types.SimpleNamespace()
        torch_module.bfloat16 = "bf16"
        transformers_module = types.ModuleType("transformers")

        class Model:
            loads = 0

            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                cls.loads += 1
                return cls()

            def to(self, device):
                return self

            def eval(self):
                return self

        transformers_module.AutoTokenizer = Model
        transformers_module.AutoModelForCausalLM = Model
        with patch.dict(sys.modules, {"torch": torch_module, "transformers": transformers_module}):
            first = ai_planner.get_model("some/model")
            second = ai_planner.get_model("some/model")
        self.assertIs(first[0], second[0])
        self.assertIs(first[1], second[1])
        self.assertEqual(Model.loads, 2)  # one tokenizer + one model, loaded once


class AIPlannerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="ai_user", password="test-password")
        cls.other = User.objects.create_user(username="other_user", password="test-password")
        PlanItem.objects.create(user=cls.user, title="Open item")
        PlanItem.objects.create(user=cls.user, title="Done item", is_completed=True)
        PlanItem.objects.create(user=cls.other, title="Someone else's item")
        cls.url = reverse("planner:ai-planner")

    def setUp(self):
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_get_shows_form_and_nav_link(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suggest a plan")
        self.assertContains(response, 'href="%s"' % self.url)

    def test_post_shows_generated_plan(self):
        result = parse_response(GOOD_RESPONSE)
        with patch("planner.views.generate_plan", return_value=result) as generate:
            response = self.client.post(self.url, {"request_text": "  Plan   my day "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finish the report")
        self.assertContains(response, "Buy groceries after lunch.")
        self.assertContains(response, "The report is due tomorrow.")
        generate.assert_called_once_with("Plan my day", [])

    def test_include_plan_items_sends_only_own_open_items(self):
        with patch("planner.views.generate_plan", return_value=parse_response(GOOD_RESPONSE)) as generate:
            self.client.post(self.url, {"request_text": "Plan", "include_plan_items": "on"})
        generate.assert_called_once_with("Plan", ["Open item"])

    def test_empty_input_shows_form_error_without_calling_model(self):
        with patch("planner.views.generate_plan") as generate:
            blank = self.client.post(self.url, {"request_text": "   "})
            control_only = self.client.post(self.url, {"request_text": "\u200b\u200b"})
        self.assertEqual(blank.status_code, 200)
        self.assertContains(blank, "This field is required.")
        self.assertEqual(control_only.status_code, 200)
        self.assertContains(control_only, "describe what you need")
        generate.assert_not_called()

    @override_settings(AI_PLANNER_MAX_INPUT_CHARS=30)
    def test_too_long_input_shows_form_error(self):
        with patch("planner.views.generate_plan") as generate:
            response = self.client.post(self.url, {"request_text": "x" * 31})
        self.assertContains(response, "under 30")
        generate.assert_not_called()

    def test_model_errors_show_message_instead_of_crashing(self):
        for error in [AIUnavailableError(), AIGenerationError(), AIOutputError()]:
            with self.subTest(error=type(error).__name__):
                with patch("planner.views.generate_plan", side_effect=error):
                    response = self.client.post(self.url, {"request_text": "Plan my day"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, error.user_message)

    def test_model_text_is_html_escaped(self):
        result = PlannerResult(priority="<script>alert(1)</script>", schedule=["<b>x</b>"], reason="r")
        with patch("planner.views.generate_plan", return_value=result):
            response = self.client.post(self.url, {"request_text": "Plan"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_incomplete_result_shows_notice(self):
        result = PlannerResult(priority="A", schedule=["Do A"], reason="", truncated=True)
        with patch("planner.views.generate_plan", return_value=result):
            response = self.client.post(self.url, {"request_text": "Plan"})
        self.assertContains(response, "looks incomplete")
