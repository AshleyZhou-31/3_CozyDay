"""CozyDay A8 Stage 1: deterministic sentence-safe paragraph chunking.

Public interface: load_knowledge_base, validate_knowledge_base,
fixed_length_chunks, overlapping_paragraph_chunks, hybrid_topic_chunks,
validate_chunks, build_all_chunks.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'cozyday_knowledge_base.json'
SENTENCE_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z“"\']|\d)')

def load_knowledge_base(path=None):
    """Return records, using a path independent of the current working directory."""
    with open(Path(path) if path is not None else DATA_PATH, encoding='utf-8') as file:
        return json.load(file)

def word_count(text):
    return len(text.split())

def split_sentences(text):
    """Split paragraphs only after terminal punctuation, preserving full sentences."""
    if not text.strip():
        return []
    parts = SENTENCE_RE.split(text.strip())
    if not all(re.search(r'[.!?][”"\']?$', s) for s in parts):
        raise ValueError('Text has missing terminal punctuation or ambiguous sentence boundaries')
    return parts

def validate_knowledge_base(records):
    assert isinstance(records, list) and len(records) >= 20, 'At least 20 paragraphs required'
    ids = [r['id'] for r in records]
    assert len(ids) == len(set(ids)), 'Duplicate paragraph IDs'
    assert all(isinstance(r.get('title'), str) and r['title'].strip() for r in records)
    assert all(isinstance(r.get('topic'), str) and r['topic'].strip() for r in records)
    assert all(isinstance(r.get('body'), str) and r['body'].strip() for r in records)
    counts = [word_count(r['body']) for r in records]
    assert all(80 <= n <= 200 for n in counts), f'Paragraph length outside 80-200: {counts}'
    total = sum(counts)
    assert 2000 <= total <= 5000, f'Expected 2000-5000 words, got {total}'
    for r in records:
        split_sentences(r['body'])
    return {'paragraphs':len(records),'total_words':total,'min_words':min(counts),'max_words':max(counts),'unique_ids':len(set(ids))}

def make_chunk(strategy, number, source, text, topic):
    return {'chunk_id': f'{strategy.upper()}_{number:03d}', 'strategy':strategy,
            'source_ids':list(source),'topic':topic,'text':text,'word_count':word_count(text)}

def fixed_length_chunks(records, target_words=130):
    """Greedily pack complete sentences to ~target_words; a long sentence stays whole."""
    if target_words < 1: raise ValueError('target_words must be positive')
    output, buffer, sources = [], [], []
    def flush():
        if buffer:
            output.append(make_chunk('fixed',len(output)+1,sources,' '.join(buffer),'mixed'))
            buffer.clear(); sources.clear()
    for r in records:
        for sentence in split_sentences(r['body']):
            if buffer and word_count(' '.join(buffer))+word_count(sentence)>target_words:
                flush()
            buffer.append(sentence)
            if not sources or sources[-1] != r['id']: sources.append(r['id'])
    flush()
    return output

def overlapping_paragraph_chunks(records, window=2, stride=1):
    """Adjacent complete paragraphs; default P1+P2, P2+P3, etc."""
    if window < 1 or stride < 1: raise ValueError('window and stride must be positive')
    result=[]
    for start in range(0,len(records),stride):
        group=records[start:start+window]
        if len(group)<window: break
        result.append(make_chunk('overlap',len(result)+1,[r['id'] for r in group],
                                 '\n\n'.join(r['body'] for r in group),
                                 group[0]['topic'] if len({r['topic'] for r in group})==1 else 'mixed'))
    return result

def hybrid_topic_chunks(records, max_words=230):
    """Group *complete paragraphs* within a shared topic, respecting max_words.

    Paragraphs longer than max_words remain intact. Never combine different topics.
    """
    if max_words < 1: raise ValueError('max_words must be positive')
    chunks=[]; group=[]; words=0; current_topic=None
    def flush():
        nonlocal words
        if group:
            chunks.append(make_chunk('hybrid',len(chunks)+1,[r['id'] for r in group],
                                     '\n\n'.join(r['body'] for r in group),current_topic))
            group.clear(); words=0
    for r in records:
        n=word_count(r['body'])
        if group and (r['topic']!=current_topic or words+n>max_words): flush()
        current_topic=r['topic']; group.append(r); words+=n
    flush()
    return chunks

def validate_chunks(records, chunks, strategy):
    assert chunks, f'{strategy}: no chunks produced'
    assert len({c['chunk_id'] for c in chunks})==len(chunks)
    lookup={r['id']:r for r in records}
    assert all(c['text'] and c['source_ids'] for c in chunks)
    assert all(all(sid in lookup for sid in c['source_ids']) for c in chunks)
    assert all(c['word_count']==word_count(c['text']) for c in chunks)
    if strategy in ('overlap','hybrid'):
        # Every component must be a complete, unmodified paragraph.
        for c in chunks:
            expected='\n\n'.join(lookup[sid]['body'] for sid in c['source_ids'])
            assert c['text']==expected, f'Truncated paragraph: {c["chunk_id"]}'
    if strategy=='hybrid':
        assert all(len({lookup[sid]['topic'] for sid in c['source_ids']})==1 for c in chunks)
    if strategy=='fixed':
        original=[s for r in records for s in split_sentences(r['body'])]
        reconstructed=[s for c in chunks for s in split_sentences(c['text'])]
        assert original==reconstructed, 'Fixed chunking dropped or modified a sentence'
    assert set(sid for c in chunks for sid in c['source_ids'])==set(lookup), 'Missing paragraph coverage'
    return True

def build_all_chunks(records):
    strategies={'fixed':fixed_length_chunks(records),
                'overlap':overlapping_paragraph_chunks(records),
                'hybrid':hybrid_topic_chunks(records)}
    for name,chunks in strategies.items(): validate_chunks(records,chunks,name)
    return strategies

if __name__=='__main__':
    data=load_knowledge_base()
    print('KB:',validate_knowledge_base(data))
    for name,chunks in build_all_chunks(data).items():
        print(name, len(chunks),'chunks', 'example:',chunks[0]['chunk_id'],chunks[0]['source_ids'])
