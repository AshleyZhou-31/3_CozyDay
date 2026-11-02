"""CozyDay Stage 3: one documented, deterministic scoring rubric.

Every evaluation row in every experiment (main grid, scaling, improvement
before/after) is scored by exactly these functions, so scores are comparable.
Nothing here calls a model; the rubric is rule-based and fully reproducible.

Context-quality score (0-3), from the retrieved chunks' source paragraph IDs
versus the query's expected evidence IDs in queries.py (the FIRST expected ID
is the primary evidence paragraph):
    3  every expected evidence paragraph appears in the retrieved context
    2  the primary evidence paragraph appears, but not all expected ones
    1  only a non-primary expected paragraph appears
    0  no expected evidence paragraph appears

Answer-quality score (0-3): the number of the query's three key points that
the final answer states. A key point counts as stated when the answer contains
at least one of its listed phrases (case-insensitive). Key points are written
from the expected evidence paragraphs, so an answer scores high only when it
reproduces what the evidence says. An answer that says the context is
insufficient is flagged ``abstained`` and scored only on the key points it
actually states (normally 0).

Limits: phrase matching rewards content, not fluency, and can miss a correct
answer worded in unexpected terms or credit a phrase used incorrectly. Rows
whose automatic score looks wrong are discussed in the notes column and in
rag_analysis.md rather than silently re-scored.
"""
from __future__ import annotations

import re

KEY_POINTS = {
    'Q1': [
        ('break the paper into concrete steps',
         ['choose a topic', 'find readings', 'find sources', 'outline', 'first version',
          'first draft', 'draft', 'revise', 'citations']),
        ('separate milestones from individual actions / observable completion',
         ['milestone', 'observable', 'completion criterion', 'individual action',
          'work session', 'checkable']),
        ('estimate durations conservatively, allow extra time, note dependencies',
         ['conservative', 'extra time', 'unpredictable', 'dependenc', 'estimate', 'buffer']),
    ],
    'Q2': [
        ('start from the earliest firm deadline',
         ['earliest', 'firm deadline', 'closest deadline', 'nearest deadline',
          'soonest deadline']),
        ('estimate remaining work and break the biggest obligation into small actions',
         ['remaining work', 'how much work', 'break the biggest', 'small actions',
          'smaller actions', 'smaller tasks', 'minimum effort']),
        ('weigh consequences / importance, or renegotiate a flexible deadline',
         ['consequence', 'importance', 'important', 'renegotiat', 'must-do']),
    ],
    'Q3': [
        ('start from fixed obligations and realistic available time',
         ['fixed obligation', 'class meeting', 'work shift', 'time left', 'available time',
          'available hours', 'appointments']),
        ('spread review across several sessions with retrieval practice',
         ['spaced', 'multiple days', 'across several', 'spread', 'retrieval practice',
          'self-test', 'self test', 'several sessions', 'series of sessions']),
        ('make study blocks specific and leave slack or review progress',
         ['achievable action', 'specific', 'unscheduled', 'buffer', 'compare planned',
          'checkpoint', 'breaks', 'practice problems', 'review mistakes']),
    ],
    'Q4': [
        ('share only what teammates need (deliverable, person, deadline)',
         ['deliverable', 'responsible person', 'only what', 'need to know',
          'teammates need', 'meeting time']),
        ('keep private or confidential details out of what is shared',
         ['private', 'confidential', 'sensitive', 'personal detail', 'hidden notes',
          'contact information']),
        ('check exports and settings, use neutral titles or keep sensitive content outside',
         ['verify', 'inspect', 'review', 'privacy settings', 'neutral', 'outside the tool',
          'approved channel']),
    ],
    'Q5': [
        ('completion counts are descriptive, not a measure of effort or success',
         ['not how much effort', 'descriptive', 'does not measure', 'not a measure',
          'indicator', 'rather than definitive', 'not definitive']),
        ('compare with estimates, deadlines, categories or trends',
         ['estimate', 'categories', 'category', 'trend', 'pattern', 'compare']),
        ('report structure: completed, upcoming deadlines, in progress, blocked',
         ['completed', 'approaching', 'in progress', 'blocked', 'decisions',
          'group by', 'upcoming']),
    ],
}

_ABSTAIN_PATTERNS = [
    r'does not contain enough', r'not enough information', r'insufficient',
    r"(?:doesn't|does not) (?:contain|provide|include|mention)",
    r'cannot (?:confidently )?answer', r"can't (?:confidently )?answer",
    r'no (?:relevant )?information', r'not (?:clearly )?(?:stated|specified|mentioned)',
]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def retrieved_source_ids(retrieved_chunks, chunk_lookup_for_strategy):
    """Ordered, de-duplicated original paragraph IDs behind the retrieved chunks."""
    seen = []
    for chunk in retrieved_chunks:
        for source_id in chunk_lookup_for_strategy[chunk['chunk_id']]['source_ids']:
            if source_id not in seen:
                seen.append(source_id)
    return seen


def context_score(source_ids, expected_ids):
    """0-3 context-quality score; see module docstring."""
    _require(len(expected_ids) >= 1, 'expected_ids must not be empty')
    got = set(source_ids)
    covered = [eid for eid in expected_ids if eid in got]
    if len(covered) == len(expected_ids):
        return 3
    if expected_ids[0] in got:
        return 2
    if covered:
        return 1
    return 0


def evidence_recall(source_ids, expected_ids):
    """Fraction of expected evidence paragraphs present in the retrieved context."""
    _require(len(expected_ids) >= 1, 'expected_ids must not be empty')
    got = set(source_ids)
    return sum(1 for eid in expected_ids if eid in got) / len(expected_ids)


def is_abstention(answer):
    text = (answer or '').lower()
    return any(re.search(pattern, text) for pattern in _ABSTAIN_PATTERNS)


def answer_score(query_id, answer):
    """(score 0-3, list of key-point labels the answer states)."""
    _require(query_id in KEY_POINTS, f'No key points defined for {query_id}')
    text = (answer or '').lower()
    hit = [label for label, phrases in KEY_POINTS[query_id]
           if any(phrase in text for phrase in phrases)]
    return len(hit), hit


def ends_cleanly(answer):
    """True when the answer finishes on terminal punctuation (not cut off mid-sentence)."""
    text = (answer or '').strip()
    return bool(text) and text[-1] in '.!?)"\'\u201d'
