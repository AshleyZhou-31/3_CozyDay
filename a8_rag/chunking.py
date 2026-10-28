"""CozyDay Stage 1: deterministic, sentence-safe, traceable chunking.

Public interfaces and chunk keys are documented in README.md. No model downloads
or third-party runtime dependencies are needed. Validation raises ValueError,
even when Python is run with -O.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'cozyday_knowledge_base.json'
STRATEGIES = ('fixed', 'overlap', 'hybrid')
# Only these related fine topics share an overlapping-paragraph section.
# Other labels form their own sections; distinct unknown labels are never merged.
OVERLAP_SECTIONS = {
    'Task Creation': 'Task Organization',
    'Categories': 'Task Organization',
    'Priorities': 'Deadline and Priority Planning',
    'Deadlines': 'Deadline and Priority Planning',
    'Reminders': 'Deadline and Priority Planning',
    'Analytics': 'Progress Review and Reporting',
    'Reports': 'Progress Review and Reporting',
}
_SENTENCE_END = re.compile(r'''[.!?]+[”"'’)]*(?=\s+[A-Z0-9“"'‘]|$)''')
_TERMINAL = re.compile(r'''[.!?][”"'’)]*$''')
_ABBREVIATIONS = {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'e.g.', 'i.e.', 'vs.', 'etc.'}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _positive_integer(value, name):
    _require(type(value) is int and value > 0, f'{name} must be a positive integer')


def load_knowledge_base(path=None):
    """Load JSON; the default data path is relative to this module, not the cwd.

    An explicitly supplied relative path is resolved against the caller's cwd.
    """
    with open(DATA_PATH if path is None else Path(path), encoding='utf-8') as file:
        return json.load(file)


def word_count(text):
    """Count whitespace-separated body-text tokens, excluding record metadata."""
    return len(text.split())


def split_sentences(text):
    """Conservative English splitter for this curated corpus, preserving quotes.

    Common titles, initials, dotted abbreviations and decimal numbers are not
    split. Ambiguous boundaries may stay together (a soft-size overflow is safer
    than cutting a sentence). This is not a general-purpose NLP tokenizer.
    """
    _require(isinstance(text, str), 'Sentence input must be a string')
    text = text.strip()
    if not text:
        return []
    _require(bool(_TERMINAL.search(text)), 'Text must end with sentence punctuation')
    sentences = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        end = match.end()
        prefix = text[:match.start() + 1]
        token = prefix.rsplit(None, 1)[-1].lower()
        if end < len(text) and match.group().startswith('.'):
            # Be conservative around abbreviations and author initials.
            if (token in _ABBREVIATIONS
                    or re.search(r'(?:\b[a-z]\.){2,}$', token)
                    or re.fullmatch(r'[A-Z]\.', prefix.rsplit(None, 1)[-1])):
                continue
        sentences.append(text[start:end].strip())
        start = end
    _require(not text[start:].strip(), 'Unrecognized terminal sentence boundary')
    _require(bool(sentences), 'No complete sentences found')
    return sentences


def _validate_records(records):
    """Validate schema for full corpora and small Stage 2 scaling subsets."""
    _require(isinstance(records, list) and bool(records), 'Expected a nonempty record list')
    ids = []
    for index, record in enumerate(records):
        _require(isinstance(record, dict), f'Record {index} must be an object')
        for key in ('id', 'title', 'topic', 'body'):
            value = record.get(key)
            _require(isinstance(value, str) and bool(value.strip()),
                     f'Record {index}: {key} must be a nonempty string')
        _require(record['id'] == record['id'].strip(), 'IDs must not have surrounding whitespace')
        split_sentences(record['body'])
        ids.append(record['id'])
    _require(len(ids) == len(set(ids)), 'Duplicate paragraph IDs')


def validate_knowledge_base(records):
    """Check the full assignment corpus; use chunkers directly for small subsets."""
    _validate_records(records)
    _require(len(records) >= 20, 'At least 20 paragraphs required')
    counts = [word_count(record['body']) for record in records]
    _require(all(80 <= count <= 200 for count in counts),
             f'Paragraph length outside 80-200: {counts}')
    total = sum(counts)
    _require(2000 <= total <= 5000, f'Expected 2000-5000 words, got {total}')
    return {'paragraphs': len(records), 'total_words': total,
            'min_words': min(counts), 'max_words': max(counts), 'unique_ids': len(records)}


def make_chunk(strategy, number, source, text, topic):
    return {'chunk_id': f'{strategy.upper()}_{number:03d}', 'strategy': strategy,
            'source_ids': list(source), 'topic': topic, 'text': text,
            'word_count': word_count(text)}


def fixed_length_chunks(records, target_words=130):
    """Greedily pack whole sentences to a soft word cap within each fine topic.

    A topic change flushes the buffer. An indivisible long sentence stays whole.
    """
    _validate_records(records)
    _positive_integer(target_words, 'target_words')
    output, buffer, sources = [], [], []
    current_topic = None
    words = 0

    def flush():
        nonlocal words
        if buffer:
            output.append(make_chunk('fixed', len(output) + 1, sources,
                                     ' '.join(buffer), current_topic))
            buffer.clear()
            sources.clear()
            words = 0

    for record in records:
        if current_topic != record['topic']:
            flush()
        current_topic = record['topic']
        for sentence in split_sentences(record['body']):
            size = word_count(sentence)
            if buffer and words + size > target_words:
                flush()
            buffer.append(sentence)
            words += size
            if not sources or sources[-1] != record['id']:
                sources.append(record['id'])
    flush()
    return output


def _section(topic):
    # Tag mapped labels to avoid collisions with arbitrary unmapped topic names.
    return ('section', OVERLAP_SECTIONS[topic]) if topic in OVERLAP_SECTIONS else ('topic', topic)


def _overlap_label(group):
    topics = {record['topic'] for record in group}
    return group[0]['topic'] if len(topics) == 1 else _section(group[0]['topic'])[1]


def overlapping_paragraph_chunks(records, window=2, stride=1):
    """Slide over adjacent complete paragraphs inside related semantic sections.

    Require 1 <= stride <= window, and stride < window when window > 1, so
    multi-paragraph windows overlap. A short section stays intact. If regular
    windows leave an uncovered tail, append a full window anchored at the end.
    """
    _validate_records(records)
    _positive_integer(window, 'window')
    _positive_integer(stride, 'stride')
    _require(stride <= window and (window == 1 or stride < window),
             'stride must be smaller than window (window=1 requires stride=1)')
    sections = []
    for record in records:
        if not sections or _section(record['topic']) != _section(sections[-1][-1]['topic']):
            sections.append([])
        sections[-1].append(record)
    result = []
    for section in sections:
        last_start = max(0, len(section) - window)
        starts = list(range(0, last_start + 1, stride))
        if starts[-1] != last_start:
            starts.append(last_start)
        for start in starts:
            group = section[start:start + window]
            result.append(make_chunk('overlap', len(result) + 1,
                                     [record['id'] for record in group],
                                     '\n\n'.join(record['body'] for record in group),
                                     _overlap_label(group)))
    return result


def hybrid_topic_chunks(records, max_words=230):
    """Pack whole consecutive paragraphs with the same fine topic and soft cap.

    A single paragraph longer than max_words remains intact. No overlap is added.
    """
    _validate_records(records)
    _positive_integer(max_words, 'max_words')
    chunks, group = [], []
    words = 0
    current_topic = None

    def flush():
        nonlocal words
        if group:
            chunks.append(make_chunk('hybrid', len(chunks) + 1,
                                     [record['id'] for record in group],
                                     '\n\n'.join(record['body'] for record in group), current_topic))
            group.clear()
            words = 0

    for record in records:
        size = word_count(record['body'])
        if group and (record['topic'] != current_topic or words + size > max_words):
            flush()
        current_topic = record['topic']
        group.append(record)
        words += size
    flush()
    return chunks


def validate_chunks(records, chunks, strategy):
    """Check IDs, metadata, per-chunk provenance, order, coverage and boundaries.

    Parameters are not encoded in chunks: this checks structural correctness,
    not whether a particular word cap/window configuration was requested.
    """
    _validate_records(records)
    _require(strategy in STRATEGIES, f'Unknown strategy: {strategy}')
    _require(isinstance(chunks, list) and bool(chunks), f'{strategy}: no chunks produced')
    lookup = {record['id']: record for record in records}
    positions = {record['id']: index for index, record in enumerate(records)}
    original = [(sentence, record['id']) for record in records
                for sentence in split_sentences(record['body'])]
    sentence_cursor = 0
    flat_ids = []
    previous_start = -1
    for number, chunk in enumerate(chunks, 1):
        _require(isinstance(chunk, dict), 'Each chunk must be an object')
        _require(chunk.get('chunk_id') == f'{strategy.upper()}_{number:03d}',
                 'Chunk IDs must be sequential and strategy-prefixed')
        _require(chunk.get('strategy') == strategy, 'Incorrect strategy metadata')
        text, source_ids = chunk.get('text'), chunk.get('source_ids')
        _require(isinstance(text, str) and bool(text.strip()), 'Empty chunk text')
        _require(isinstance(source_ids, list) and bool(source_ids), 'Empty source IDs')
        _require(all(isinstance(sid, str) and sid in lookup for sid in source_ids),
                 'Unknown source paragraph ID')
        _require(len(source_ids) == len(set(source_ids)), 'Duplicate source ID in a chunk')
        _require(type(chunk.get('word_count')) is int and chunk['word_count'] == word_count(text),
                 'Incorrect word count')
        topics = {lookup[sid]['topic'] for sid in source_ids}
        if strategy == 'overlap':
            _require(len({_section(topic) for topic in topics}) == 1,
                     'Overlap chunk merges unrelated sections')
            expected_topic = _overlap_label([lookup[sid] for sid in source_ids])
        else:
            _require(len(topics) == 1, f'{strategy}: chunk merges fine topics')
            expected_topic = lookup[source_ids[0]]['topic']
        _require(chunk.get('topic') == expected_topic, 'Incorrect topic metadata')
        if strategy == 'fixed':
            sentences = split_sentences(text)
            expected = original[sentence_cursor:sentence_cursor + len(sentences)]
            _require(sentences == [sentence for sentence, _ in expected],
                     'Fixed chunking dropped, duplicated, reordered or modified a sentence')
            expected_ids = list(dict.fromkeys(sid for _, sid in expected))
            _require(source_ids == expected_ids, 'Fixed chunk text/source IDs disagree')
            _require(text == ' '.join(sentences), 'Unexpected fixed chunk separators')
            sentence_cursor += len(sentences)
        else:
            expected_text = '\n\n'.join(lookup[sid]['body'] for sid in source_ids)
            _require(text == expected_text, 'Truncated or modified source paragraph')
            indices = [positions[sid] for sid in source_ids]
            _require(indices == list(range(indices[0], indices[0] + len(indices))),
                     'Source paragraphs must be adjacent and ordered')
            if strategy == 'overlap':
                _require(indices[0] > previous_start, 'Overlap windows duplicated or reordered')
                previous_start = indices[0]
        flat_ids.extend(source_ids)
    _require(set(flat_ids) == set(lookup), 'Missing paragraph coverage')
    if strategy == 'fixed':
        _require(sentence_cursor == len(original), 'Missing final sentences')
    if strategy == 'hybrid':
        _require(flat_ids == list(lookup), 'Hybrid paragraphs duplicated or reordered')
    return True


def build_all_chunks(records):
    """Build and validate all defaults, including small nonempty scaling subsets."""
    strategies = {'fixed': fixed_length_chunks(records),
                  'overlap': overlapping_paragraph_chunks(records),
                  'hybrid': hybrid_topic_chunks(records)}
    for name, chunks in strategies.items():
        validate_chunks(records, chunks, name)
    return strategies


if __name__ == '__main__':
    data = load_knowledge_base()
    print('KB:', validate_knowledge_base(data))
    for name, chunks in build_all_chunks(data).items():
        print(name, len(chunks), 'chunks', 'example:', chunks[0]['chunk_id'], chunks[0]['source_ids'])
