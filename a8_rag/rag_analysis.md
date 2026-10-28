# P1 A8 — Stage 1: Knowledge Base & Chunking

**Owner:** Lin Gao | **Project:** Team 3 CozyDay | **Scope:** Steps 1.1 and 1.2 only.

## Dataset and validation

- Original English paragraphs: **30** (unique IDs `P001`–`P030`).
- Body-text words, using whitespace-separated token counting: **3111**.
- Words per paragraph: **97–112**, within the required 80–200 range.
- Each paragraph has an ID, descriptive title, topical label, and plain-text body.
- Topics include task creation, categories, priorities, deadlines, reminders, study planning, wellness, privacy, search, analytics, reports, authentication, common questions, calendar coordination, and accessibility.
- Content is explanatory and deliberately avoids claiming features are implemented in the CozyDay web app when that has not been established.

## Chunking methods

| Strategy | Parameters | Chunk count | Sentence / topic handling |
|---|---|---:|---|
| Fixed length | `target_words=130` | **26** | Greedy packing of complete sentences; never cuts a sentence, though boundaries may cross paragraphs or topics. |
| Overlapping paragraphs | `window=2, stride=1` | **29** | Adjacent complete paragraph pairs: P001+P002, P002+P003, etc. Adjacent topics may differ. |
| Hybrid (topic-aware) | `max_words=230` | **15** | Packs complete consecutive paragraphs only when their topic matches and size fits. Never merges unrelated topics. |

### Boundary rules

Original knowledge-base paragraphs are author-defined semantic units, each with one focus and topic. Sentence splitting operates at punctuation followed by whitespace and a new sentence-start character, without modifying original sentence text. The fixed method packs sentences until the next whole sentence would exceed its soft word target. Consequently, an exceptionally long sentence could exceed that target rather than be truncated. Overlapping chunks duplicate complete paragraphs for neighboring context; this increases storage and embedding cost. Hybrid chunks preserve complete paragraphs and topic purity; the maximum is soft for a single unusually long paragraph.

### Validation

`validate_knowledge_base` checks count, 2,000–5,000 overall word limit, 80–200 words per paragraph, unique IDs, nonempty IDs/titles/topics/bodies, and sentence punctuation. `validate_chunks` checks unique chunk IDs, nonempty chunk text, source paragraph coverage, valid source IDs, exact preservation of original paragraphs for overlap/hybrid, exact sentence order and content for fixed, and same-topic membership for hybrid. `test_stage1.py` provides seven standalone regression tests including expected failures for malformed inputs.

### Stage 2 handoff

```python
from chunking import load_knowledge_base, build_all_chunks
records = load_knowledge_base()
chunks_by_strategy = build_all_chunks(records)
for chunk in chunks_by_strategy['hybrid']:
    print(chunk['chunk_id'], chunk['source_ids'], chunk['text'])
```

Chunk object keys: `chunk_id`, `strategy`, `source_ids`, `topic`, `text`, `word_count`. The next teammate should embed `text` and retain identifiers for diagnostics. **No embeddings, retrieval, LLM inference, evaluation, or model downloads have been run or claimed in this stage.** Chunk counts reflect the frozen original dataset and default parameters. External submission instructions take precedence if modified by the instructor.
