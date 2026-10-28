# P1 A8 — Stage 1: Knowledge Base and Chunking

**Owner:** Lin Gao | **Project:** Team 3 CozyDay | **Scope:** Steps 1.1 and 1.2.

## Dataset

The corpus contains 30 author-defined English paragraphs: 3,111 body-text words, 97–112 words per paragraph, with 30 unique IDs and 30 distinct titles. Counting uses whitespace-separated body-text tokens; titles, IDs, topics, and repeated overlap content do not inflate the dataset size. Each paragraph has one focus and a fine-topic label. Paragraph IDs, titles, ordering, topics, and bodies are unchanged by the code-review corrections.

The 15 fine topics cover task creation, categories, priorities, deadlines, reminders, study planning, wellness, privacy, search, analytics, reports, authentication, common questions, calendar coordination, and accessibility. This is explanatory student-planning guidance, not a claim that every discussed feature exists in the deployed CozyDay application. It does not include live user task data.

## Three chunking strategies

| Strategy | Defaults | Chunks | Words per chunk | Total indexed words |
|---|---|---:|---:|---:|
| Fixed length | `target_words=130` | 30 | 72–130 | 3,111 |
| Overlapping paragraphs | `window=2, stride=1` | 19 | 199–216 | 3,942 |
| Hybrid | `max_words=230` | 15 | 199–216 | 3,111 |

These are the corrected defaults, replacing the earlier 26/29/15 counts. The 80–200-word requirement applies to original paragraphs, not combined chunks.

### Fixed-length boundaries

Pack complete sentences greedily until adding the next sentence would exceed 130 words. Flush before a fine-topic change, even if the buffer is short. This keeps the strategy driven by a word-size target without merging different fine topics. Sentences may cross paragraph boundaries within the same topic. A sentence longer than the target remains intact as a documented soft-cap exception. No overlap is introduced and no source sentence is lost, repeated, or reordered.

Sentence splitting is conservative English punctuation handling with closing quotes, common abbreviations, initials, and decimals. The curated corpus is the supported source; arbitrary NLP segmentation is not claimed. Ambiguous boundaries can remain grouped instead of risking a cut inside a sentence. An exact independent normalized-text comparison in the tests guards against content loss even if the splitter itself changes.

### Overlap boundaries and semantic sections

The Canvas rule against unrelated-topic merges applies to overlap as well as fixed/hybrid. Pairing every neighboring paragraph across the entire corpus would violate that rule. Conversely, the corpus has only two paragraphs per fine topic, so pairing only identical labels would produce no real sliding overlap and would duplicate hybrid's default output.

Instead, slide across **adjacent paragraphs in related semantic sections**. The only cross-label combinations allowed by `OVERLAP_SECTIONS` are:

| Fine topics | Related section | Why the passages belong together |
|---|---|---|
| Task Creation, Categories | Task Organization | Defining tasks, breaking assignments down, and organizing those same tasks by context. |
| Priorities, Deadlines, Reminders | Deadline and Priority Planning | Deciding what to do first, working backward from deadlines, and timing reminders to act on the plan. |
| Analytics, Reports | Progress Review and Reporting | Interpreting recorded progress and communicating that progress in summaries. |

Every other label forms its own section. Different unknown labels are kept separate. Sections are contiguous runs in the input order; matching labels elsewhere in the document are not pulled together. For example, no chunk bridges Wellness and Privacy, Privacy and Search, or Authentication and Common Questions.

Default windows are P001+P002, P002+P003, P003+P004 in Task Organization, then a new run starts at P005. Each neighboring pair of two-paragraph windows in a long section shares one full paragraph (50% of the paragraph positions). There are eight within-section transitions with this real overlap. A two-paragraph section produces one complete pair; a singleton produces one complete paragraph. No artificial duplication is added just to create an overlap at a semantic boundary.

For custom windows, require `1 <= stride < window`; `window=1, stride=1` is an explicit no-overlap special case. If a stride leaves a tail, append the last full window anchored at the section end. A section shorter than the window stays intact once. These rules preserve coverage for odd lengths, small subsets, and oversized windows. The default indexing total includes 831 repeated words; the knowledge base itself remains 3,111 words.

### Hybrid boundaries

Group complete, consecutive paragraphs only when their **fine topic is identical** and the combined size is at most 230 words. There is no overlap. A single overlong paragraph stays whole. This gives 15 nonoverlapping topic groups, different from overlap's broader related sections and fixed's sentence/word-driven boundaries.

## Automated validation and testing

`validate_knowledge_base` checks the record schema, nonempty string IDs/titles/topics/bodies, duplicate IDs, terminal punctuation, minimum 20 paragraphs, individual 80–200-word limits, and total 2,000–5,000-word limits.

`validate_chunks` checks sequential strategy-prefixed IDs, matching strategy and topic metadata, valid ordered source IDs, exact word counts, nonempty output, and complete source coverage. Fixed validation maps each chunk's exact sentence sequence back to its own source IDs, not just a global set. Overlap/hybrid validation compares exact original paragraphs and verifies adjacency; hybrid also disallows duplicate or reordered paragraphs. Overlap windows must progress in document order and remain in a related section. Exceptions are explicit `ValueError`s and cannot be disabled by optimized Python.

The 26 unit tests cover these invariants, malformed inputs, lost/duplicated sentences, wrong provenance, quotes/abbreviations/decimals, soft-cap exceptions, genuine overlap, unrelated-topic boundaries, tail coverage, parameter rejection, small scaling subsets, path independence, and validation under `python -O`. Structural validation cannot prove semantic relevance from labels alone: the section mapping above and the authored passages must be reviewed together. It also does not infer a requested size/window setting from chunk metadata; those defaults are checked directly by regression tests.

## Stage 2 handoff

From `a8_rag/`:

```python
from chunking import load_knowledge_base, validate_knowledge_base, build_all_chunks
records = load_knowledge_base()
validate_knowledge_base(records)
chunks_by_strategy = build_all_chunks(records)
texts = [chunk['text'] for chunk in chunks_by_strategy['hybrid']]
```

The public function names and chunk keys remain `chunk_id`, `strategy`, `source_ids`, `topic`, `text`, and `word_count`. Embed `text`; preserve the other fields for retrieval diagnostics. Corrected chunk boundaries require regenerating any pre-review chunks. Paragraph IDs and dataset paths remain unchanged. Default IDs are deterministic; different parameter configurations require separate index namespaces. No embeddings, retrieval, generation, experimental results, or later-stage rubric answers are claimed here.
