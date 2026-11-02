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


---

# P1 A8 — Stage 3: Experiments, Failure Analysis and Improvement

**Owner:** Shivani Shivani | **Project:** Team 3 CozyDay | **Scope:** Part 2 (system experiments) and Part 3 (failure analysis and improvement).

All numbers below come from `results/stage3_evaluations.csv` (one row per evaluation, with full retrieved chunk text) and the `results/stage3_summary_*.csv` / `stage3_improvement_*.csv` tables derived from it. The notebook (`rag_system.ipynb`, sections 10 to 17) shows the same tables and the full text of every failure case.

## Experimental setup

* **Grid:** 3 embedding models (MiniLM 384 dimensions, MPNet 768, BGE-large 1024) x 3 chunking strategies (fixed, overlap, hybrid) x the 5 shared queries = **45 evaluations**, Top-K = 3, cosine similarity.
* **Locked across every row:** generation model `Qwen/Qwen2.5-3B-Instruct`, greedy decoding with `max_new_tokens=300`, the Stage 2 prompt, and the five queries. Only the improvement runs change the system instruction, and they are labelled as such.
* **Recorded per row:** embedding model, dimensions, chunking strategy, query, retrieved chunk IDs and source paragraphs, full retrieved text, similarity scores, context-quality score, final answer, answer-quality score, key points stated, four latencies, and notes.
* **Hardware:** one local run on a MacBook Air (Apple Silicon). Latencies are single-run wall-clock times and include warm-up effects, so small latency differences are noise.

## Scoring rubric (`scoring.py`)

One rule-based rubric scores every row, including the scaling and improvement runs.

| Score | Context quality (0-3) | Answer quality (0-3) |
|---|---|---|
| 3 | every expected evidence paragraph is in the retrieved context | all three key points stated |
| 2 | the primary evidence paragraph is present, not all of them | two key points |
| 1 | only a secondary evidence paragraph is present | one key point |
| 0 | no expected evidence paragraph | none |

Expected evidence IDs and notes are in `queries.py`. Each query has three key points, each a short list of phrases drawn from its evidence paragraphs; a key point counts as stated when the answer contains any of its phrases. **Limits:** phrase matching rewards the evidence's own wording and favours longer answers that touch more phrases; it can miss a correct paraphrase. Where this affects a conclusion it is stated below. The rubric is deterministic and tested (`test_stage3.py`).

## Results: 45 evaluations

Mean context score is 2.96 of 3 and mean answer score 2.47 of 3. 45 of 45 rows contain retrieved chunks. No answer said the context was insufficient. Per-row values are in the notebook (section 11) and the CSV.

### Embedding size

| Model | Dimensions | Context | Evidence recall | Answer | Median query-embedding | Median search | Median generation | Index time, fixed chunks | Vector storage, fixed chunks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MiniLM | 384 | 2.87 | 0.96 | 2.40 | 0.17 s | 0.4 ms | 13.9 s | 0.34 s | 46 KB |
| MPNet | 768 | 3.00 | 1.00 | 2.47 | 0.08 s | 0.4 ms | 16.0 s | 0.61 s | 92 KB |
| BGE-large | 1024 | 3.00 | 1.00 | 2.53 | 0.11 s | 0.4 ms | 15.1 s | 1.34 s | 123 KB |

**Does a larger vector always perform better? No.** MPNet matched BGE-large on retrieval: both retrieved every expected evidence paragraph for all 15 of their rows. MiniLM made the only retrieval misses (Q2 with overlap and hybrid chunks). Answer scores rise slightly with size, but a 0.07 gap is one row in fifteen. Query-embedding time does not rise with size in these runs (MiniLM was slowest, most likely warm-up), and search takes under a millisecond for all sizes, while generation takes 14 to 16 seconds. In this setup embedding size matters mainly for index time and storage, which grow with dimension. The conclusion applies to this small corpus and these five queries.

### Chunking strategy

| Strategy | Context | Evidence recall | Answer | Retrieved context per query | Mean generation |
|---|---:|---:|---:|---:|---:|
| Fixed | 3.00 | 1.00 | 2.40 | 326 words | 14.4 s |
| Hybrid | 2.93 | 0.98 | 2.73 | 625 words | 13.4 s |
| Overlap | 2.93 | 0.98 | 2.27 | 620 words | 13.1 s |

Fixed chunking has the best retrieval score but hybrid gives the best answers. Hybrid chunks are whole same-topic paragraph groups, so the model receives each recommendation complete, with about twice the context of fixed chunks. Overlap supplies about as much context as hybrid but as overlapping windows, and it scored lower; in the small-model Q2 case an off-topic window outranked the right paragraphs. With five queries these are observations, not proven causes. Generation time is almost unrelated to how much context is retrieved (correlation -0.08) and follows how many tokens the model writes: Q1 and Q5 answers average 21 s and 18 s, Q2 and Q3 about 8 s.

### Configuration view (mean answer score, 5 queries each)

| | Fixed | Overlap | Hybrid |
|---|---:|---:|---:|
| MiniLM (384) | 2.2 | 2.2 | 2.8 |
| MPNet (768) | 2.4 | 2.2 | 2.8 |
| BGE-large (1024) | 2.6 | 2.4 | 2.6 |

### By query

| Query | Context | Answer | Mean generation | Note |
|---|---:|---:|---:|---|
| Q1 paper breakdown | 3.00 | 2.78 | 21.2 s | all 9 answers cut off at the token limit |
| Q2 competing deadlines | 2.78 | 2.44 | 8.2 s | the only retrieval misses |
| Q3 weekly study plan | 3.00 | 2.00 | 7.7 s | one key point missed in all 9 configurations |
| Q4 sharing a plan privately | 3.00 | 2.67 | 12.9 s | |
| Q5 analytics report | 3.00 | 2.44 | 18.1 s | 4 answers cut off |

## Dataset scaling: 10 paragraphs vs 30

The subset keeps ten evidence-bearing paragraphs (P001, P002, P006, P011, P012, P015, P016, P019, P020, P021), so the test measures competition from distractors, not whether the answer exists. Queries, models, Top-K and scoring are unchanged. The subset omits P005 and P025, expected evidence for Q2, so Q2 cannot score 3 there: the raw context score falls from 3.0 to 2.8 for seven configurations, but that is an artifact. Scoring only the evidence that exists in the subset (`stage3_summary_scaling_attainable.csv`), recall is 1.0 at both sizes in all nine configurations.

A generation check with the large model and hybrid chunks on the subset scored 2.4 against 2.6 on the full data and took about the same time (14.0 s against 13.8 s), which is within the variation of five rows. **Conclusion:** at this scale the collection size did not change retrieval or answer quality. Thirty paragraphs is too small to show retrieval degrading, and no claim is made about larger collections.

## Failure analysis

The baseline scored 111 of 135 possible key points. All 24 missed key points had their key phrases present in the retrieved context (notebook section 15), so the weak link is generation, not retrieval, apart from the Q2 retrieval misses.

### Failure 1: Q3, a key point omitted in all nine configurations (large / fixed shown)

* **Query:** "How do I build a weekly study plan and prepare for my exam using spaced review?" Expected evidence: P011, P012.
* **Retrieved:** FIXED_011, FIXED_012, FIXED_002 (scores 0.743, 0.740, 0.626). The first chunk begins "A weekly plan begins with fixed obligations such as class meetings, work shifts, and appointments."
* **Observed failure:** the answer never says to start from fixed obligations and available time. It also reuses a sentence about conservative estimates and unpredictable research from the third chunk, a Task Creation paragraph with no connection to exam study.
* **Root cause: generation-model limitation and prompt design.** The evidence was in the context, and the omission happens in all nine configurations, so it is not an embedding or chunking effect. The prompt does not tell the model to ignore irrelevant passages, which lets the P002 chunk leak into the answer.

### Failure 2: Q1, answers cut off mid-sentence (large / fixed shown)

* **Query:** "I have a big semester paper due in a few weeks. How should I break it down into tasks in CozyDay?" Expected evidence: P002, P001.
* **Retrieved:** the correct paragraphs; context score 3 in all nine configurations.
* **Observed failure:** every Q1 answer stops in the middle of a sentence. Across all 45 rows, 13 answers (29 percent) are cut off (9 for Q1, 4 for Q5); two Q1 answers lose the "estimate durations conservatively" point and two Q5 answers lose the report-structure point.
* **Root cause: prompt design combined with the locked decoding limit.** The baseline prompt invites long numbered explanations (Q1 answers average 232 words), which cannot finish inside `max_new_tokens=300`. Retrieval is not involved.

### Failure 3: Q2, a missed evidence paragraph and an invented example (small / overlap)

* **Query:** "I have three assignments due this week and they all feel urgent. How do I decide what to work on first?" Expected evidence: P006, P005, P025.
* **Retrieved:** OVERLAP_003 (P003 and P004), OVERLAP_004 (P005 and P006), OVERLAP_002 (P002 and P003), scores 0.555, 0.538, 0.534. Context score 2: the primary evidence P006 is present, but P025 ("What should I work on first today?") is missing.
* **Observed failure:** the top-ranked chunk is a Categories window. The answer invents an example about a course grade and a scholarship that appears nowhere in the context, and says an assignment with work already done is less urgent, which the evidence does not say.
* **Root cause: embedding choice and chunking for the retrieval miss, generation for the invention.** MPNet and BGE-large retrieved P005, P006 and P025 for the same query, and the small model with fixed chunks also found P025, so the miss comes from the 384-dimension model combined with overlap or hybrid chunking. The invented example is a generation limitation; the instruction to use only the context did not prevent it.

## Improvement: change only the system prompt

The three failures point at the prompt: answers too long to finish, irrelevant chunks leaking in, invented content. The generation model, decoding settings, retrieval, Top-K, chunks and queries are identical; only the system instruction changes. Each variant reran all 45 evaluations with the same rubric. Two variants were tried and both are reported; choosing between two variants on the same five queries is mild tuning on the evaluation set, so the numbers are indicative.

* **Variant 1, `concise-complete`:** at most five short numbered steps, under 150 words, ignore irrelevant passages, add nothing outside the context.
* **Variant 2, `complete-within-limit`:** a complete answer of at most 170 words, in the context's own wording, starting with the first recommended step, adding nothing outside the context.

### Before and after (45 rows each)

| Version | Context | Answer | Answers ending cleanly | Mean words | Mean generation |
|---|---:|---:|---:|---:|---:|
| Before: baseline prompt | 2.96 | 2.47 | 71% | 153 | 13.6 s |
| After: variant 1 | 2.96 | 2.20 | 100% | 73 | 7.4 s |
| After: variant 2 | 2.96 | 2.22 | 100% | 106 | 9.9 s |

| Query | Before | Variant 1 | Variant 2 |
|---|---:|---:|---:|
| Q1 | 2.78 | 2.56 | 2.22 |
| Q2 | 2.44 | 1.78 | 2.00 |
| Q3 | 2.00 | 2.11 | 2.33 |
| Q4 | 2.67 | 3.00 | 2.33 |
| Q5 | 2.44 | 1.56 | 2.22 |

### What changed

* **Fixed:** truncation (71 percent to 100 percent of answers finishing) and latency (down 27 to 46 percent). The invented scholarship example in the Q2 failure row is gone under both variants (that row scored 2 before, 1 under variant 1, and 3 under variant 2).
* **Partly fixed:** the Q3 omission. Variant 2, which starts with the first recommended step, stated the fixed-obligations point in 3 of 9 configurations (0 of 9 before); variant 1 in 1 of 9. Variant 1 improved the Q4 sharing point from 6 to 9 of 9 and the Q1 conservative-estimates point from 7 to 9.
* **Made worse:** overall answer score fell from 2.47 to 2.20 and 2.22. Against the baseline, variant 1 scored better on 6 rows and worse on 17; variant 2 better on 4 and worse on 15. Variant 1 lost the Q2 earliest-deadline point (9 to 6 of 9) and the Q5 report-structure point (7 to 3), and variant 2 lost the Q2 consequences point (8 to 2) and the Q4 sharing point (6 to 3). The 13 answers that used to be cut off scored 2.69 before but only 2.23 and 2.31 once shortened.

### Interpretation

The prompt change fixed completeness and reliability but not coverage, so on the answer-quality score it is not an improvement. Shortening the answers removes details the evidence contains, and the rubric, which counts evidence phrases, penalises that; some of the drop is the rubric favouring longer answers rather than worse advice. Recovering coverage without losing completeness probably needs either a longer decoding limit, which the shared contract locks, or a different lever such as re-ranking or filtering off-topic chunks before generation. These were not tested.

## Limitations

* Five queries and one run per configuration, so single-row differences (0.07 of a mean) are within noise; latency numbers are single runs on one machine with warm-up effects.
* Answer scoring is phrase-based (see the rubric); it was not replaced by human grading.
* The corpus has 30 paragraphs, so the scaling result does not extend to large collections.
* The improvement used the same five queries it was evaluated on and tried two variants.
* Retrieval quality is near the ceiling, so these experiments mostly discriminate on generation behaviour.
