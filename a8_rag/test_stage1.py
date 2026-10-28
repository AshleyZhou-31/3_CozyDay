"""Stage 1 regression tests; run with python test_stage1.py or unittest discover."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from chunking import (
    build_all_chunks, fixed_length_chunks, hybrid_topic_chunks,
    load_knowledge_base, overlapping_paragraph_chunks, split_sentences,
    validate_chunks, validate_knowledge_base,
)


def fixture(count=5):
    return [{'id': f'T{index}', 'title': f'Title {index}', 'topic': 'Study Planning',
             'body': f'Study item {index} starts here. Review the recorded notes.'}
            for index in range(count)]


class Stage1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_knowledge_base()

    def test_dataset(self):
        self.assertEqual(validate_knowledge_base(self.data), {
            'paragraphs': 30, 'total_words': 3111, 'min_words': 97,
            'max_words': 112, 'unique_ids': 30})
        self.assertEqual(len({record['title'] for record in self.data}), 30)

    def test_dataset_rejects_malformed_fields(self):
        for field in ('id', 'title', 'topic', 'body'):
            for bad in ('', '  ', None, 42):
                with self.subTest(field=field, bad=bad):
                    records = copy.deepcopy(self.data)
                    records[0][field] = bad
                    with self.assertRaises(ValueError):
                        validate_knowledge_base(records)
            records = copy.deepcopy(self.data)
            del records[0][field]
            with self.assertRaises(ValueError):
                validate_knowledge_base(records)

    def test_duplicate_ids_fail(self):
        records = copy.deepcopy(self.data)
        records[1]['id'] = records[0]['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_knowledge_base(records)

    def test_paragraph_length_limits(self):
        for count in (79, 201):
            records = copy.deepcopy(self.data)
            records[0]['body'] = ' '.join(['word'] * count) + '.'
            with self.assertRaisesRegex(ValueError, '80-200'):
                validate_knowledge_base(records)

    def test_full_dataset_size_limits(self):
        with self.assertRaisesRegex(ValueError, 'At least 20'):
            validate_knowledge_base(self.data[:19])
        for count, words in ((20, 80), (30, 180)):
            records = fixture(count)
            for record in records:
                record['body'] = ' '.join(['word'] * words) + '.'
            with self.assertRaisesRegex(ValueError, '2000-5000'):
                validate_knowledge_base(records)

    def test_sentence_quotes_abbreviations_and_decimal(self):
        self.assertEqual(split_sentences('He said “Stop.” Then he left.'),
                         ['He said “Stop.”', 'Then he left.'])
        self.assertEqual(split_sentences('Dr. Chen estimated 2.5 hours. Start now!'),
                         ['Dr. Chen estimated 2.5 hours.', 'Start now!'])
        self.assertEqual(split_sentences('Ask A. Chen for advice. Review it.'),
                         ['Ask A. Chen for advice.', 'Review it.'])

    def test_missing_terminal_punctuation_fails(self):
        records = copy.deepcopy(self.data)
        records[0]['body'] = records[0]['body'].rstrip('.')
        with self.assertRaises(ValueError):
            validate_knowledge_base(records)

    def test_default_counts_and_schema(self):
        result = build_all_chunks(self.data)
        self.assertEqual({name: len(chunks) for name, chunks in result.items()},
                         {'fixed': 30, 'overlap': 19, 'hybrid': 15})
        for name, chunks in result.items():
            self.assertTrue(validate_chunks(self.data, chunks, name))
            for chunk in chunks:
                self.assertEqual(set(chunk), {'chunk_id', 'strategy', 'source_ids',
                                             'topic', 'text', 'word_count'})

    def test_fixed_preserves_original_body_independently(self):
        # Do not use the production sentence splitter as the preservation oracle.
        chunks = fixed_length_chunks(self.data)
        expected = ' '.join(' '.join(record['body'].split()) for record in self.data)
        actual = ' '.join(' '.join(chunk['text'].split()) for chunk in chunks)
        self.assertEqual(actual, expected)
        self.assertTrue(all(chunk['word_count'] <= 130 for chunk in chunks))

    def test_fixed_flushes_at_unrelated_topic(self):
        records = fixture(2)
        records[1]['topic'] = 'Privacy'
        chunks = fixed_length_chunks(records, target_words=1000)
        self.assertEqual([chunk['source_ids'] for chunk in chunks], [['T0'], ['T1']])

    def test_fixed_long_sentence_stays_whole(self):
        records = fixture(1)
        records[0]['body'] = ' '.join(['Long'] * 160) + '.'
        chunks = fixed_length_chunks(records, target_words=10)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['text'], records[0]['body'])
        self.assertTrue(validate_chunks(records, chunks, 'fixed'))

    def test_overlap_actually_overlaps(self):
        records = fixture(4)
        chunks = overlapping_paragraph_chunks(records)
        self.assertEqual([chunk['source_ids'] for chunk in chunks],
                         [['T0', 'T1'], ['T1', 'T2'], ['T2', 'T3']])
        frozen = overlapping_paragraph_chunks(self.data)
        self.assertEqual(frozen[0]['source_ids'], ['P001', 'P002'])
        self.assertEqual(frozen[1]['source_ids'], ['P002', 'P003'])
        self.assertEqual(frozen[2]['source_ids'], ['P003', 'P004'])

    def test_overlap_stops_between_wellness_and_privacy(self):
        records = self.data[12:16]
        chunks = overlapping_paragraph_chunks(records)
        self.assertEqual([chunk['source_ids'] for chunk in chunks],
                         [['P013', 'P014'], ['P015', 'P016']])
        self.assertTrue(validate_chunks(records, chunks, 'overlap'))

    def test_overlap_unknown_topics_not_merged(self):
        records = fixture(2)
        records[0]['topic'] = 'Unlisted A'
        records[1]['topic'] = 'Unlisted B'
        self.assertEqual(len(overlapping_paragraph_chunks(records)), 2)

    def test_overlap_tail_singleton_and_large_window(self):
        records = fixture(6)
        chunks = overlapping_paragraph_chunks(records, window=3, stride=2)
        self.assertEqual([chunk['source_ids'] for chunk in chunks],
                         [['T0', 'T1', 'T2'], ['T2', 'T3', 'T4'], ['T3', 'T4', 'T5']])
        self.assertTrue(validate_chunks(records, chunks, 'overlap'))
        for size, window in ((1, 2), (2, 5), (6, 1)):
            records = fixture(size)
            chunks = overlapping_paragraph_chunks(records, window=window)
            self.assertTrue(validate_chunks(records, chunks, 'overlap'))

    def test_invalid_chunker_parameters(self):
        for bad in (0, -1, 1.5, '2', True):
            for function, key in ((fixed_length_chunks, 'target_words'),
                                  (hybrid_topic_chunks, 'max_words'),
                                  (overlapping_paragraph_chunks, 'window'),
                                  (overlapping_paragraph_chunks, 'stride')):
                with self.subTest(function=function.__name__, key=key, bad=bad):
                    with self.assertRaises(ValueError):
                        function(self.data, **{key: bad})
        for window, stride in ((2, 2), (2, 3), (1, 2)):
            with self.assertRaises(ValueError):
                overlapping_paragraph_chunks(self.data, window, stride)

    def test_hybrid_whole_paragraph_cap_and_no_repetition(self):
        records = fixture(4)
        records[2]['topic'] = records[3]['topic'] = 'Privacy'
        for cap in (1, 25, 1000):
            chunks = hybrid_topic_chunks(records, max_words=cap)
            self.assertEqual([sid for chunk in chunks for sid in chunk['source_ids']],
                             [record['id'] for record in records])
            self.assertTrue(validate_chunks(records, chunks, 'hybrid'))

    def test_fixed_wrong_provenance_rejected(self):
        chunks = fixed_length_chunks(self.data)
        chunks[0]['source_ids'], chunks[1]['source_ids'] = (
            chunks[1]['source_ids'], chunks[0]['source_ids'])
        with self.assertRaisesRegex(ValueError, 'source IDs'):
            validate_chunks(self.data, chunks, 'fixed')

    def test_fixed_lost_or_duplicated_sentence_rejected(self):
        for remove in (True, False):
            chunks = fixed_length_chunks(self.data)
            sentences = split_sentences(chunks[0]['text'])
            chunks[0]['text'] = ' '.join(sentences[1:] if remove else sentences + [sentences[0]])
            chunks[0]['word_count'] = len(chunks[0]['text'].split())
            with self.assertRaises(ValueError):
                validate_chunks(self.data, chunks, 'fixed')

    def test_incorrect_chunk_metadata_rejected(self):
        for field, bad in (('chunk_id', 'bad'), ('strategy', 'other'), ('topic', 'other'),
                           ('text', ' '), ('source_ids', ['NO_SUCH_ID']),
                           ('word_count', 1), ('word_count', True)):
            with self.subTest(field=field):
                chunks = hybrid_topic_chunks(self.data)
                chunks[0][field] = bad
                with self.assertRaises(ValueError):
                    validate_chunks(self.data, chunks, 'hybrid')
        with self.assertRaises(ValueError):
            validate_chunks(self.data, hybrid_topic_chunks(self.data), 'unknown')

    def test_modified_paragraph_and_missing_coverage_rejected(self):
        for name in ('overlap', 'hybrid'):
            chunks = build_all_chunks(self.data)[name]
            chunks[0]['text'] += ' Extra text.'
            chunks[0]['word_count'] = len(chunks[0]['text'].split())
            with self.assertRaises(ValueError):
                validate_chunks(self.data, chunks, name)
            chunks = build_all_chunks(self.data)[name][:-1]
            with self.assertRaisesRegex(ValueError, 'coverage'):
                validate_chunks(self.data, chunks, name)

    def test_nonadjacent_and_reordered_paragraphs_rejected(self):
        records = fixture(4)
        chunks = overlapping_paragraph_chunks(records)
        for ids in (['T0', 'T2'], ['T1', 'T0']):
            modified = copy.deepcopy(chunks)
            modified[0]['source_ids'] = ids
            lookup = {record['id']: record for record in records}
            modified[0]['text'] = '\n\n'.join(lookup[sid]['body'] for sid in ids)
            modified[0]['word_count'] = len(modified[0]['text'].split())
            with self.assertRaisesRegex(ValueError, 'adjacent'):
                validate_chunks(records, modified, 'overlap')

    def test_chunkers_support_small_scaling_subsets(self):
        for count in (1, 5, 10):
            self.assertEqual(set(build_all_chunks(self.data[:count])), {'fixed', 'overlap', 'hybrid'})

    def test_empty_inputs_rejected(self):
        for function in (validate_knowledge_base, build_all_chunks, fixed_length_chunks,
                         overlapping_paragraph_chunks, hybrid_topic_chunks):
            with self.assertRaises(ValueError):
                function([])

    def test_default_load_independent_of_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(load_knowledge_base(), self.data)
            finally:
                os.chdir(previous)

    def test_validation_remains_active_with_optimization(self):
        result = subprocess.run([sys.executable, '-O', '-c',
            'from chunking import *\n'
            'r=load_knowledge_base(); r[0]["id"]=""\n'
            'try: validate_knowledge_base(r)\n'
            'except ValueError: pass\n'
            'else: raise RuntimeError("Validation disabled")\n'],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
