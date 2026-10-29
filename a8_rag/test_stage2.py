"""Stage 2 regression tests; run with python test_stage2.py or unittest discover."""
import json
import unittest

import numpy as np

from chunking import build_all_chunks, load_knowledge_base
from embedding import (EMBEDDING_MODELS, EXPECTED_DIMENSIONS, EMBEDDINGS_DIR,
                        load_embedding_model, embed_query)
from retrieval import build_chunk_lookup, similarity_search
from queries import TEST_QUERIES, validate_test_queries
from generation import GENERATION_MODEL, DECODING_SETTINGS, SYSTEM_INSTRUCTION, build_prompt


class CachedEmbeddingsTests(unittest.TestCase):
    """Checks the committed results/embeddings/ cache without reloading any model."""

    @classmethod
    def setUpClass(cls):
        cls.records = load_knowledge_base()
        cls.chunks_by_strategy = build_all_chunks(cls.records)

    def test_all_nine_combinations_cached(self):
        for model_key in EMBEDDING_MODELS:
            for strategy in self.chunks_by_strategy:
                base = EMBEDDINGS_DIR / f"{model_key}__{strategy}"
                self.assertTrue(base.with_suffix(".npy").exists(), f"missing {base}.npy")
                self.assertTrue(base.with_suffix(".json").exists(), f"missing {base}.json")

    def test_cached_shapes_and_normalization(self):
        for model_key, expected_dim in EXPECTED_DIMENSIONS.items():
            for strategy, chunks in self.chunks_by_strategy.items():
                base = EMBEDDINGS_DIR / f"{model_key}__{strategy}"
                vectors = np.load(base.with_suffix(".npy"))
                meta = json.loads(base.with_suffix(".json").read_text())
                self.assertEqual(vectors.shape, (len(chunks), expected_dim))
                self.assertEqual(meta["chunk_ids"], [c["chunk_id"] for c in chunks])
                self.assertEqual(meta["model_name"], EMBEDDING_MODELS[model_key])
                norms = np.linalg.norm(vectors, axis=1)
                self.assertTrue(np.allclose(norms, 1.0, atol=1e-4),
                                f"{model_key}/{strategy}: vectors are not unit-normalized")


class RetrievalMathTests(unittest.TestCase):
    """Pure-logic checks for ranking and chunk lookup; no model is loaded."""

    def test_similarity_search_ranks_by_cosine(self):
        chunk_ids = ["A", "B", "C"]
        vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.70710678, 0.70710678]], dtype="float32")
        query = np.array([1.0, 0.0], dtype="float32")
        results, latency = similarity_search(query, chunk_ids, vectors, top_k=2)
        self.assertEqual([r["chunk_id"] for r in results], ["A", "C"])
        self.assertAlmostEqual(results[0]["score"], 1.0, places=5)
        self.assertGreaterEqual(latency, 0.0)

    def test_similarity_search_top_k_capped_at_corpus_size(self):
        chunk_ids = ["A", "B"]
        vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
        results, _ = similarity_search(np.array([1.0, 0.0], dtype="float32"), chunk_ids, vectors, top_k=5)
        self.assertEqual(len(results), 2)

    def test_similarity_search_rejects_bad_top_k(self):
        with self.assertRaises(ValueError):
            similarity_search(np.array([1.0]), ["A"], np.array([[1.0]]), top_k=0)

    def test_build_chunk_lookup_round_trips_chunk_text(self):
        records = load_knowledge_base()
        chunks_by_strategy = build_all_chunks(records)
        lookup = build_chunk_lookup(chunks_by_strategy)
        for strategy, chunks in chunks_by_strategy.items():
            for chunk in chunks:
                self.assertEqual(lookup[strategy][chunk["chunk_id"]]["text"], chunk["text"])


class TestQueriesTests(unittest.TestCase):
    def setUp(self):
        self.records = load_knowledge_base()

    def test_five_queries_with_unique_ids_and_evidence(self):
        self.assertEqual(len(TEST_QUERIES), 5)
        ids = [item["query_id"] for item in TEST_QUERIES]
        self.assertEqual(len(ids), len(set(ids)), "duplicate query_id")
        for item in TEST_QUERIES:
            self.assertTrue(item["query"].strip())
            self.assertTrue(item["expected_evidence_ids"])
            self.assertTrue(item["topics"])

    def test_evidence_ids_exist_in_knowledge_base(self):
        self.assertTrue(validate_test_queries(self.records))

    def test_evidence_ids_rejected_when_missing(self):
        missing_id = TEST_QUERIES[0]["expected_evidence_ids"][0]
        bad_records = [r for r in self.records if r["id"] != missing_id]
        with self.assertRaises(ValueError):
            validate_test_queries(bad_records)


class GenerationContractTests(unittest.TestCase):
    """Checks the locked model/decoding contract and prompt construction; no model is loaded."""

    def test_generation_model_and_decoding_are_locked(self):
        self.assertEqual(GENERATION_MODEL, "Qwen/Qwen2.5-3B-Instruct")
        self.assertFalse(DECODING_SETTINGS["do_sample"], "decoding must be deterministic (greedy)")
        self.assertEqual(DECODING_SETTINGS["num_beams"], 1)

    def test_prompt_includes_system_instruction_and_context(self):
        chunks = [{"chunk_id": "FIXED_001", "text": "Example chunk text."}]
        messages = build_prompt(chunks, "What is an example?")
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], SYSTEM_INSTRUCTION)
        self.assertIn("does not contain enough information", SYSTEM_INSTRUCTION.lower())
        self.assertIn("guessing", SYSTEM_INSTRUCTION.lower())
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("FIXED_001", messages[1]["content"])
        self.assertIn("Example chunk text.", messages[1]["content"])
        self.assertIn("What is an example?", messages[1]["content"])

    def test_prompt_handles_empty_context_without_crashing(self):
        messages = build_prompt([], "Any question?")
        self.assertIn("no context retrieved", messages[1]["content"])

    def test_build_prompt_rejects_empty_query(self):
        with self.assertRaises(ValueError):
            build_prompt([], "   ")


class LiveEmbeddingModelTests(unittest.TestCase):
    """One real model load/encode to catch breakage the cached-file checks above cannot see.

    Deliberately limited to the smallest model so this suite stays fast; the notebook's own
    executed smoke test is the full nine-combination proof.
    """

    def test_small_model_loads_with_expected_dimension(self):
        info = load_embedding_model("small")
        self.assertEqual(info["dimension"], EXPECTED_DIMENSIONS["small"])
        self.assertIn(info["device"], ("cpu", "cuda", "mps"))

        vector, latency = embed_query(info, "A quick dimension check query.")
        self.assertEqual(vector.shape, (EXPECTED_DIMENSIONS["small"],))
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=4)
        self.assertGreaterEqual(latency, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
