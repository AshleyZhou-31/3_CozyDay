"""Tests for the local RAG engine. No model is ever downloaded or loaded:
sentence-transformers/transformers are replaced with small fakes, following
the same convention as test_ai_planner.py's FakeModel/FakeTokenizer."""

import sys
import types
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from . import rag_engine
from .rag_planner import RAGPlannerError, generate_rag_plan


class FakeEncoder:
    """Stands in for a SentenceTransformer: maps known texts to fixed vectors
    so cosine ranking is deterministic and checkable."""

    def __init__(self, vectors_by_text, default=(0.0, 0.0, 1.0)):
        self.vectors_by_text = vectors_by_text
        self.default = default

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True):
        import numpy as np

        rows = [self.vectors_by_text.get(text, self.default) for text in texts]
        vectors = np.array(rows, dtype="float32")
        if normalize_embeddings:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            vectors = vectors / norms
        return vectors


class FakeBatch(dict):
    def to(self, device):
        return self


class FakeIds:
    def __init__(self, length):
        self.shape = (1, length)


class FakeGenTokenizer:
    chat_template = "fake-template"

    def __init__(self, prompt_token_count=5):
        self.prompt_token_count = prompt_token_count
        self.messages = None

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        self.messages = messages
        return "|".join(f"{m['role']}:{m['content']}" for m in messages)

    def __call__(self, prompt_text, return_tensors):
        return FakeBatch({"input_ids": FakeIds(self.prompt_token_count)})

    def decode(self, tokens, skip_special_tokens):
        return self.text


class FakeGenModel:
    device = "cpu"

    def __init__(self, text="Priority: test\nSchedule:\n1. Do it.\nReason: because.", new_tokens=20, error=None):
        self.text = text
        self.new_tokens = new_tokens
        self.error = error

    def generate(self, **kwargs):
        if self.error:
            raise self.error
        return [list(range(5 + self.new_tokens))]


def _fake_embedding_info(vectors_by_text):
    return {
        "key": "medium",
        "model_name": "sentence-transformers/all-mpnet-base-v2",
        "model": FakeEncoder(vectors_by_text),
        "dimension": 3,
        "device": "cpu",
        "load_time_seconds": 0.0,
    }


def _fake_generation_info(answer_text="Priority: test\nSchedule:\n1. Do it.\nReason: because.", error=None):
    tokenizer = FakeGenTokenizer()
    tokenizer.text = answer_text
    return {
        "model_name": "Qwen/Qwen2.5-3B-Instruct",
        "model": FakeGenModel(text=answer_text, error=error),
        "tokenizer": tokenizer,
        "device": "cpu",
        "load_time_seconds": 0.0,
    }


def _fake_engine(chunk_text="Split a semester paper into milestones.", answer_text=None, chunks=None):
    chunk_ids = ["HYBRID_001"] if chunks is None else [c["chunk_id"] for c in chunks]
    chunk_lookup = (
        {"HYBRID_001": {"chunk_id": "HYBRID_001", "text": chunk_text}}
        if chunks is None
        else {c["chunk_id"]: c for c in chunks}
    )
    import numpy as np

    vectors = np.array([[1.0, 0.0, 0.0]] * len(chunk_ids), dtype="float32") if chunk_ids else np.zeros((0, 3), dtype="float32")
    return {
        "chunk_ids": chunk_ids,
        "vectors": vectors,
        "chunk_lookup": chunk_lookup,
        "embedding_info": _fake_embedding_info({"a planning question": (1.0, 0.0, 0.0)}),
        "generation_info": _fake_generation_info(
            answer_text if answer_text is not None else "Priority: test\nSchedule:\n1. Do it.\nReason: because."
        ),
    }


@override_settings(AI_PLANNER_MAX_TIME_SECONDS=5)
class AnswerQueryTests(SimpleTestCase):
    def setUp(self):
        rag_engine.clear_engine_cache()
        self.addCleanup(rag_engine.clear_engine_cache)

    def test_happy_path_returns_full_contract(self):
        with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
            result = rag_engine.answer_query("a planning question")
        self.assertIn("Priority: test", result["answer"])
        self.assertEqual(result["retrieved_chunks"][0]["id"], "HYBRID_001")
        self.assertIsInstance(result["latency_seconds"], float)
        self.assertIsNone(result["warning"])

    def test_no_chunks_retrieved_adds_warning_but_still_answers(self):
        engine = _fake_engine()
        engine["chunk_ids"] = []
        import numpy as np
        engine["vectors"] = np.zeros((0, 3), dtype="float32")
        with patch.object(rag_engine, "get_engine", return_value=engine):
            result = rag_engine.answer_query("a planning question")
        self.assertEqual(result["retrieved_chunks"], [])
        self.assertIn("No closely matching", result["warning"])

    def test_empty_generation_output_raises_output_error(self):
        engine = _fake_engine(answer_text="")
        with patch.object(rag_engine, "get_engine", return_value=engine):
            with self.assertRaises(rag_engine.RAGOutputError):
                rag_engine.answer_query("a planning question")

    def test_generation_exception_becomes_generation_error(self):
        engine = _fake_engine()
        engine["generation_info"] = _fake_generation_info(error=RuntimeError("boom, private query leak risk"))
        with patch.object(rag_engine, "get_engine", return_value=engine), self.assertLogs(
            "planner.rag_engine", "ERROR"
        ):
            with self.assertRaises(rag_engine.RAGGenerationError) as ctx:
                rag_engine.answer_query("a planning question")
        self.assertNotIn("boom", str(ctx.exception.user_message))

    def test_generation_timeout_raises_generation_error_not_hang(self):
        with patch.object(rag_engine, "_generate_with_timeout", return_value=("", 5, True)):
            with patch.object(rag_engine, "get_engine", return_value=_fake_engine()):
                with self.assertRaises(rag_engine.RAGGenerationError) as ctx:
                    rag_engine.answer_query("a planning question", max_time_seconds=0.01)
        self.assertIn("too long", ctx.exception.user_message)

    def test_generate_with_timeout_returns_promptly_not_after_full_slow_call(self):
        """PR #31 review (Ashley): the previous implementation used
        ThreadPoolExecutor as a context manager, so __exit__'s
        shutdown(wait=True) blocked until the slow worker finished even
        after future.result() had already raised TimeoutError -- making
        the soft timeout a no-op. This calls the REAL
        _generate_with_timeout (not mocked) against a genuinely slow fake
        generate_answer and asserts on wall-clock time that it returns
        near max_time_seconds, not after the full slow call."""
        import time as time_module

        def _slow_generate_answer(generation_info, chunks, query):
            time_module.sleep(0.6)
            return "late answer", 0.6

        with patch("generation.generate_answer", side_effect=_slow_generate_answer):
            start = time_module.perf_counter()
            answer, latency, timed_out = rag_engine._generate_with_timeout(
                _fake_generation_info(), [], "a planning question", max_time_seconds=0.15
            )
            elapsed = time_module.perf_counter() - start

        # Drain: block until the orphaned background thread actually
        # releases _generate_lock, so this test doesn't leave a stale lock
        # that intermittently stalls whichever test runs next.
        rag_engine._generate_lock.acquire()
        rag_engine._generate_lock.release()

        self.assertTrue(timed_out)
        self.assertEqual(answer, "")
        self.assertLess(
            elapsed, 0.4,
            f"took {elapsed:.2f}s to return -- the soft timeout is not actually "
            "bounding the caller's wait (this is the bug Ashley found in PR #31: "
            "ThreadPoolExecutor used as a context manager blocks on "
            "shutdown(wait=True) until the slow worker finishes). A 1.0s threshold "
            "was too loose: the buggy implementation returns in ~0.6s (bounded by "
            "the slow call itself, not the 0.15s timeout) and would have passed "
            "that check too.",
        )

    def test_retrieval_exception_becomes_retrieval_error(self):
        with patch("embedding.embed_query", side_effect=RuntimeError("model crashed")), patch.object(
            rag_engine, "get_engine", return_value=_fake_engine()
        ):
            with self.assertRaises(rag_engine.RAGRetrievalError):
                rag_engine.answer_query("a planning question")

    def test_engine_build_failure_is_cached_not_retried_every_call(self):
        with patch.object(rag_engine, "_build_engine", side_effect=rag_engine.RAGUnavailableError()) as build:
            with self.assertRaises(rag_engine.RAGUnavailableError):
                rag_engine.get_engine()
            with self.assertRaises(rag_engine.RAGUnavailableError):
                rag_engine.get_engine()
        self.assertEqual(build.call_count, 1)

    def test_missing_a8_rag_packages_raise_unavailable(self):
        rag_engine.clear_engine_cache()
        with patch.dict(sys.modules, {"chunking": None}):
            with self.assertRaises(rag_engine.RAGUnavailableError):
                rag_engine.get_engine()


class GenerateRagPlanTests(SimpleTestCase):
    """planner.rag_planner.generate_rag_plan must keep the exact Stage 1 contract."""

    def test_delegates_to_engine_and_matches_stage1_contract(self):
        fake_result = {
            "answer": "Break it into steps.",
            "retrieved_chunks": [{"id": "HYBRID_001", "text": "...", "score": 0.9}],
            "latency_seconds": 0.5,
            "warning": None,
        }
        with patch("planner.rag_engine.answer_query", return_value=fake_result):
            result = generate_rag_plan("How do I plan my paper?", user=None)
        self.assertEqual(set(result.keys()), {"answer", "retrieved_chunks", "latency_seconds", "warning"})
        self.assertEqual(result["answer"], "Break it into steps.")

    def test_engine_error_propagates_as_ragplannererror(self):
        with patch("planner.rag_engine.answer_query", side_effect=RAGPlannerError("unavailable")):
            with self.assertRaises(RAGPlannerError):
                generate_rag_plan("plan my week")


class CorpusHashTests(SimpleTestCase):
    def test_same_content_same_hash(self):
        records = [{"id": "P1", "title": "T", "body": "Hello world."}]
        self.assertEqual(rag_engine._corpus_hash(records), rag_engine._corpus_hash(list(records)))

    def test_edited_text_changes_hash_even_with_same_ids(self):
        a = [{"id": "P1", "title": "T", "body": "Hello world."}]
        b = [{"id": "P1", "title": "T", "body": "Hello, world!"}]
        self.assertNotEqual(rag_engine._corpus_hash(a), rag_engine._corpus_hash(b))
