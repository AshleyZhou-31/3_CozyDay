"""CozyDay Stage 2: five shared test queries and their expected evidence.

Every one of the nine embedding/chunking smoke-test combinations in this
stage, and every Stage 3 evaluation row, must use these same five queries
unchanged (per the team's shared evaluation contract).
"""

TEST_QUERIES = [
    {
        'query_id': 'Q1',
        'query': ('I have a big semester paper due in a few weeks. How should I break it '
                  'down into tasks in CozyDay?'),
        'topics': ['Task Creation'],
        'expected_evidence_ids': ['P002', 'P001'],
        'expected_evidence_notes': (
            "P002 describes splitting a semester paper into milestone/action steps with "
            "dependencies and conservative duration estimates; P001 gives the general rule "
            "that large assignments should become several smaller, checkable tasks."
        ),
    },
    {
        'query_id': 'Q2',
        'query': ('I have three assignments due this week and they all feel urgent. How do '
                  'I decide what to work on first?'),
        'topics': ['Priorities', 'Common Questions'],
        'expected_evidence_ids': ['P006', 'P005', 'P025'],
        'expected_evidence_notes': (
            "P006 gives the concrete procedure for competing deadlines (earliest firm "
            "deadline, remaining work, renegotiate if possible); P005 explains urgency vs. "
            "importance; P025 answers the closely related 'what first today' question."
        ),
    },
    {
        'query_id': 'Q3',
        'query': ('How do I build a weekly study plan and prepare for my exam using spaced '
                  'review?'),
        'topics': ['Study Planning'],
        'expected_evidence_ids': ['P011', 'P012'],
        'expected_evidence_notes': (
            "P011 covers building a realistic weekly study plan around fixed obligations; "
            "P012 covers spaced, retrieval-practice-based exam preparation across sessions."
        ),
    },
    {
        'query_id': 'Q4',
        'query': ('I want to share my group project plan with teammates. How do I do that '
                  'without exposing private information?'),
        'topics': ['Privacy'],
        'expected_evidence_ids': ['P016', 'P015'],
        'expected_evidence_notes': (
            "P016 directly covers sharing plans/exports with teammates while keeping private "
            "details out; P015 gives the general rule for minimizing sensitive information "
            "in task text before anything is shared."
        ),
    },
    {
        'query_id': 'Q5',
        'query': ('How should I use my task completion analytics to write a weekly progress '
                  'report?'),
        'topics': ['Analytics', 'Reports'],
        'expected_evidence_ids': ['P019', 'P020', 'P021'],
        'expected_evidence_notes': (
            "P019/P020 explain how to interpret completion counts and patterns without "
            "over-reading them; P021 gives the structure of a weekly progress report that "
            "should be built from those same analytics."
        ),
    },
]


def validate_test_queries(records):
    """Check that every expected_evidence_id exists in the current knowledge base."""
    ids = {record['id'] for record in records}
    for item in TEST_QUERIES:
        missing = [eid for eid in item['expected_evidence_ids'] if eid not in ids]
        if missing:
            raise ValueError(f"{item['query_id']}: unknown evidence IDs {missing}")
    return True
