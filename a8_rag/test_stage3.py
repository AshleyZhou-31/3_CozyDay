"""Stage 3 regression tests; run with python test_stage3.py or unittest discover.

No model is downloaded: embedding and generation are replaced by deterministic
stand-ins so the runner, resume logic, scoring rubric, and subset handling can be
verified offline. The real experiments run through experiments.py with the real models.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import experiments
import scoring
from chunking import build_all_chunks, load_knowledge_base, validate_chunks
from embedding import EMBEDDINGS_DIR, EXPECTED_DIMENSIONS, EMBEDDING_MODELS, embed_all_combinations
from queries import TEST_QUERIES
from retrieval import build_chunk_lookup


class FakeEncoder:
    """Deterministic unit-norm vectors of the right size; stands in for SentenceTransformer."""

    def __init__(self, dim):
        self.dim = dim

    def encode(self, texts, convert_to_numpy=True, normalize_embeddings=True, **_):
        rows = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
            vec = np.random.default_rng(seed).normal(size=self.dim)
            rows.append(vec / np.linalg.norm(vec))
        return np.array(rows, dtype='float32')


def fake_model_infos():
    return {key: {'key': key, 'model_name': EMBEDDING_MODELS[key], 'model': FakeEncoder(dim),
                  'dimension': dim, 'device': 'cpu', 'load_time_seconds': 0.0}
            for key, dim in EXPECTED_DIMENSIONS.items()}


def cache_fingerprint():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(EMBEDDINGS_DIR.glob('*'))}


class ScoringTests(unittest.TestCase):
    def test_context_score_levels(self):
        expected = ['P002', 'P001']
        self.assertEqual(scoring.context_score(['P002', 'P001', 'P009'], expected), 3)
        self.assertEqual(scoring.context_score(['P002', 'P009'], expected), 2)
        self.assertEqual(scoring.context_score(['P001', 'P009'], expected), 1)
        self.assertEqual(scoring.context_score(['P009', 'P010'], expected), 0)
        with self.assertRaises(ValueError):
            scoring.context_score(['P001'], [])

    def test_evidence_recall(self):
        self.assertAlmostEqual(scoring.evidence_recall(['P006'], ['P006', 'P005', 'P025']), 1 / 3)

    def test_every_query_has_three_key_points(self):
        self.assertEqual({q['query_id'] for q in TEST_QUERIES}, set(scoring.KEY_POINTS))
        for points in scoring.KEY_POINTS.values():
            self.assertEqual(len(points), 3)
            for label, phrases in points:
                self.assertTrue(label and phrases)

    def test_answer_score_counts_key_points(self):
        answer = ('Split it into steps: choose a topic and draft an outline. Mark milestones '
                  'and estimate conservatively.')
        score, hit = scoring.answer_score('Q1', answer)
        self.assertEqual(score, 3)
        self.assertEqual(len(hit), 3)
        self.assertEqual(scoring.answer_score('Q1', 'Buy groceries.')[0], 0)
        with self.assertRaises(ValueError):
            scoring.answer_score('Q9', 'x')

    def test_ends_cleanly(self):
        self.assertTrue(scoring.ends_cleanly('Done.'))
        self.assertFalse(scoring.ends_cleanly('Each of these tasks should have a due date and ensure that each task'))
        self.assertFalse(scoring.ends_cleanly(''))

    def test_abstention_detection(self):
        self.assertTrue(scoring.is_abstention('The context does not contain enough information.'))
        self.assertFalse(scoring.is_abstention('Start with the earliest firm deadline.'))


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = load_knowledge_base()
        cls.chunks = build_all_chunks(cls.records)
        cls.lookup = build_chunk_lookup(cls.chunks)
        cls.infos = fake_model_infos()
        cls.embeddings = embed_all_combinations(cls.infos, cls.chunks, use_cache=False)

    def run_main(self, csv_path):
        fake_answer = ('Use milestones and an outline; estimate conservatively. '
                       'Share only the deliverable and keep private details out.')
        with mock.patch('rag.generate_answer', return_value=(fake_answer, 0.5)):
            return experiments.run_main_grid(self.infos, self.chunks, self.embeddings,
                                             self.lookup, {'stub': True}, csv_path=csv_path,
                                             progress=lambda *_: None)

    def test_main_grid_has_45_complete_rows_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / 'rows.csv'
            first = self.run_main(csv_path)
            self.assertEqual(len(first), 45)
            rows = experiments.read_rows(csv_path)
            self.assertEqual(len(rows), 45)
            self.assertEqual(len({r['run_id'] for r in rows}), 45)
            self.assertEqual({(r['embedding_key'], r['chunking'], r['query_id']) for r in rows},
                             {(k, s, q['query_id']) for k in self.infos for s in self.chunks
                              for q in TEST_QUERIES})
            for row in rows:
                self.assertEqual(list(row.keys()), experiments.COLUMNS)
                texts = json.loads(row['retrieved_chunk_texts'])
                self.assertEqual(len(texts), 3)
                self.assertTrue(all(t.strip() for t in texts))
                self.assertEqual(len(json.loads(row['similarity_scores'])), 3)
                self.assertEqual(int(row['dimensions']), EXPECTED_DIMENSIONS[row['embedding_key']])
                self.assertTrue(row['final_answer'])
                self.assertIn(row['context_score'], {'0', '1', '2', '3'})
            second = self.run_main(csv_path)
            self.assertEqual(second, [])
            self.assertEqual(len(experiments.read_rows(csv_path)), 45)

    def test_main_grid_requires_generation_model(self):
        with self.assertRaises(ValueError):
            experiments.run_main_grid(self.infos, self.chunks, self.embeddings, self.lookup, None,
                                      csv_path=Path(tempfile.gettempdir()) / 'unused.csv')

    def test_partial_run_resumes_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / 'rows.csv'
            self.run_main(csv_path)
            lines = csv_path.read_text().splitlines()
            csv_path.write_text('\n'.join(lines[:11]) + '\n')  # header + 10 rows
            added = self.run_main(csv_path)
            self.assertEqual(len(added), 35)
            self.assertEqual(len(experiments.read_rows(csv_path)), 45)

    def test_scaling_subset_and_retrieval_do_not_touch_full_cache(self):
        before = cache_fingerprint()
        subset, subset_chunks = experiments.build_subset(self.records)
        self.assertEqual(len(subset), 10)
        for strategy, chunks in subset_chunks.items():
            validate_chunks(subset, chunks, strategy)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / 'rows.csv'
            rows = experiments.run_scaling_retrieval(self.infos, self.records, csv_path=csv_path,
                                                     progress=lambda *_: None)
            self.assertEqual(len(rows), 45)
            self.assertTrue(all(r['dataset'] == 'subset10' and r['final_answer'] == ''
                                for r in rows))
        self.assertEqual(cache_fingerprint(), before)

    def test_prompt_variant_applies_only_inside_context_and_is_restored(self):
        import generation
        original = generation.SYSTEM_INSTRUCTION
        seen = []

        def fake(generation_info, chunks, query):
            seen.append(generation.SYSTEM_INSTRUCTION)
            return 'Use milestones.', 0.1

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch('rag.generate_answer', side_effect=fake):
            rows = experiments.run_prompt_improvement(
                self.infos, self.chunks, self.embeddings, self.lookup, {'stub': True},
                csv_path=Path(tmp) / 'rows.csv', progress=lambda *_: None)
        self.assertEqual(len(rows), 45)
        self.assertTrue(all(r['stage'] == 'improvement' and r['variant'] == 'concise-complete'
                            for r in rows))
        self.assertEqual(set(seen), {experiments.PROMPT_VARIANTS['concise-complete']})
        self.assertEqual(generation.SYSTEM_INSTRUCTION, original)
        self.assertEqual(generation.DECODING_SETTINGS['max_new_tokens'], 300)

    def test_second_variant_runs_and_summary_handles_two_variants(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch('rag.generate_answer', return_value=('Use milestones.', 0.1)):
            csv_path = Path(tmp) / 'rows.csv'
            self.run_main(csv_path)
            for variant in experiments.PROMPT_VARIANTS:
                rows = experiments.run_prompt_improvement(
                    self.infos, self.chunks, self.embeddings, self.lookup, {'stub': True},
                    csv_path=csv_path, variant=variant, progress=lambda *_: None)
                self.assertEqual(len(rows), 45)
            written = experiments.summarize(csv_path, out_dir=Path(tmp) / 'out')
            import pandas as pd
            overall = pd.read_csv(written['improvement_overall'])
            self.assertEqual(sorted(overall['version']),
                             sorted(['before_baseline_prompt'] +
                                    ['after_' + v for v in experiments.PROMPT_VARIANTS]))

    def test_prompt_variant_restored_after_error(self):
        import generation
        original = generation.SYSTEM_INSTRUCTION
        with self.assertRaises(RuntimeError):
            with experiments.prompt_variant('temporary'):
                self.assertEqual(generation.SYSTEM_INSTRUCTION, 'temporary')
                raise RuntimeError('boom')
        self.assertEqual(generation.SYSTEM_INSTRUCTION, original)

    def test_summary_files_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / 'rows.csv'
            self.run_main(csv_path)
            experiments.run_scaling_retrieval(self.infos, self.records, csv_path=csv_path,
                                              progress=lambda *_: None)
            written = experiments.summarize(csv_path, out_dir=Path(tmp) / 'out')
            self.assertEqual(set(written), {'by_embedding', 'by_chunking', 'by_configuration',
                                            'by_query', 'scaling', 'scaling_attainable'})
            for path in written.values():
                self.assertTrue(path.exists() and path.stat().st_size > 0)


class CommittedResultsTests(unittest.TestCase):
    """Gate checks on the committed Stage 3 results table (skipped if it is absent)."""

    @classmethod
    def setUpClass(cls):
        if not experiments.EVAL_CSV.exists():
            raise unittest.SkipTest('results/stage3_evaluations.csv not present')
        cls.rows = experiments.read_rows()

    def test_columns_and_unique_ids(self):
        self.assertTrue(all(list(r.keys()) == experiments.COLUMNS for r in self.rows))
        self.assertEqual(len({r['run_id'] for r in self.rows}), len(self.rows))

    def test_main_grid_is_complete_with_retrieved_chunks(self):
        main = [r for r in self.rows if r['stage'] == 'main']
        self.assertEqual(len(main), 45)
        self.assertEqual({(r['embedding_key'], r['chunking'], r['query_id']) for r in main},
                         {(k, s, q['query_id']) for k in EXPECTED_DIMENSIONS
                          for s in ('fixed', 'overlap', 'hybrid') for q in TEST_QUERIES})
        for row in main:
            self.assertEqual(len(json.loads(row['retrieved_chunk_texts'])), 3)
            self.assertTrue(row['final_answer'].strip())
            self.assertEqual(row['top_k'], '3')

    def test_scores_are_reproducible_from_the_rubric(self):
        for row in self.rows:
            if row['stage'] == 'scaling':
                continue
            self.assertEqual(scoring.answer_score(row['query_id'], row['final_answer'])[0],
                             int(float(row['answer_score'])), row['run_id'])

    def test_improvement_variants_have_full_grids(self):
        for variant in experiments.PROMPT_VARIANTS:
            rows = [r for r in self.rows if r['stage'] == 'improvement' and r['variant'] == variant]
            self.assertEqual(len(rows), 45, variant)

    def test_scaling_rows_cover_all_configurations(self):
        sub = [r for r in self.rows if r['stage'] == 'scaling']
        self.assertEqual(len(sub), 45)
        self.assertTrue(all(r['dataset'] == 'subset10' for r in sub))


if __name__ == '__main__':
    unittest.main()
