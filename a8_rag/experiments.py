"""CozyDay Stage 3: experiment runner for the A8 system experiments.

Runs the required 3 embedding models x 3 chunking strategies x 5 shared queries
grid (45 rows) with the Stage 2 pipeline, the scaling comparison, and any
variant (improvement) runs. Every row is scored by scoring.py and appended to
one CSV as soon as it finishes, so an interrupted run resumes where it stopped.

Nothing here changes the generation model, decoding settings, similarity method,
or the five queries; it only calls the frozen Stage 2 interface (rag.run_rag and
retrieval.retrieve).

Command line (from a8_rag/):
    python experiments.py main                 # 45 generation rows
    python experiments.py scaling-retrieval    # 45 retrieval-only rows on the 10-paragraph subset
    python experiments.py scaling-generation --model large --strategy hybrid
    python experiments.py improve-prompt [--variant complete-within-limit]
                                               # 45 rows with a changed prompt (before/after)
    python experiments.py summary              # write the summary CSVs from the row table
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import scoring  # noqa: E402
from chunking import build_all_chunks, load_knowledge_base  # noqa: E402
from queries import TEST_QUERIES  # noqa: E402
from retrieval import build_chunk_lookup, retrieve  # noqa: E402

RESULTS_DIR = HERE / 'results'
EVAL_CSV = RESULTS_DIR / 'stage3_evaluations.csv'

# One paragraph set shared by every scaling run: the primary evidence paragraph for
# each of the five queries plus other expected-evidence paragraphs, 10 in all. Using
# evidence-covering paragraphs keeps the comparison about dataset SIZE (how many
# distractors compete), not about whether the answer exists in the data.
SCALING_SUBSET_IDS = ['P001', 'P002', 'P006', 'P011', 'P012', 'P015', 'P016', 'P019',
                      'P020', 'P021']

COLUMNS = [
    'run_id', 'stage', 'dataset', 'variant', 'embedding_key', 'embedding_model',
    'dimensions', 'chunking', 'query_id', 'query', 'top_k',
    'retrieved_chunk_ids', 'retrieved_source_ids', 'retrieved_chunk_texts',
    'similarity_scores', 'context_score', 'evidence_recall', 'primary_evidence_retrieved',
    'final_answer', 'answer_score', 'key_points_stated', 'abstained',
    'embedding_latency_s', 'retrieval_latency_s', 'generation_latency_s', 'total_latency_s',
    'notes',
]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def make_run_id(stage, dataset, variant, model_key, strategy, query_id, top_k):
    return '|'.join([stage, dataset, variant, model_key, strategy, query_id, f'k{top_k}'])


def _auto_note(row_context_score, abstained, primary_hit, generated):
    notes = []
    if not primary_hit:
        notes.append('primary evidence paragraph not retrieved')
    elif row_context_score < 3:
        notes.append('some expected evidence missing from context')
    if generated and abstained:
        notes.append('answer says context is insufficient')
    return '; '.join(notes)


def evaluate_one(model_info, strategy, query_item, embeddings, chunk_lookup,
                 generation_info, *, stage, dataset, variant='baseline', top_k=3,
                 query_text=None, dimensions=None):
    """Retrieve, optionally generate, and score one (model, strategy, query) row.

    generation_info=None gives a retrieval-only row (used by the scaling
    retrieval sweep); the answer columns are then left empty.
    ``query_text`` lets an improvement run rewrite the query while the row still
    records the original query_id and scores against the original expected evidence.
    """
    import rag  # imported here so tests can patch rag.generate_answer

    text = query_text if query_text is not None else query_item['query']
    if generation_info is None:
        result = retrieve(text, model_info, strategy, embeddings, chunk_lookup, top_k=top_k)
        chunks = result['chunks']
        answer, gen_latency, total_latency = '', None, None
        embed_latency = result['embedding_latency_seconds']
        retr_latency = result['retrieval_latency_seconds']
    else:
        result = rag.run_rag(text, model_info, strategy, embeddings, chunk_lookup,
                             generation_info, top_k=top_k)
        chunks = result['retrieved_chunks']
        answer = result['final_answer']
        gen_latency = result['generation_latency_seconds']
        total_latency = result['total_latency_seconds']
        embed_latency = result['embedding_latency_seconds']
        retr_latency = result['retrieval_latency_seconds']

    expected = query_item['expected_evidence_ids']
    sources = scoring.retrieved_source_ids(chunks, chunk_lookup[strategy])
    ctx = scoring.context_score(sources, expected)
    primary = expected[0] in sources
    generated = generation_info is not None
    if generated:
        a_score, hit = scoring.answer_score(query_item['query_id'], answer)
        abstained = scoring.is_abstention(answer)
    else:
        a_score, hit, abstained = '', [], ''

    return {
        'run_id': make_run_id(stage, dataset, variant, model_info['key'], strategy,
                              query_item['query_id'], top_k),
        'stage': stage, 'dataset': dataset, 'variant': variant,
        'embedding_key': model_info['key'], 'embedding_model': model_info['model_name'],
        'dimensions': dimensions if dimensions is not None else model_info['dimension'],
        'chunking': strategy, 'query_id': query_item['query_id'], 'query': text,
        'top_k': top_k,
        'retrieved_chunk_ids': ';'.join(c['chunk_id'] for c in chunks),
        'retrieved_source_ids': ';'.join(sources),
        'retrieved_chunk_texts': json.dumps([c['text'] for c in chunks]),
        'similarity_scores': json.dumps([round(c['score'], 6) for c in chunks]),
        'context_score': ctx,
        'evidence_recall': round(scoring.evidence_recall(sources, expected), 4),
        'primary_evidence_retrieved': primary,
        'final_answer': answer,
        'answer_score': a_score,
        'key_points_stated': json.dumps(hit),
        'abstained': abstained,
        'embedding_latency_s': round(embed_latency, 6),
        'retrieval_latency_s': round(retr_latency, 6),
        'generation_latency_s': '' if gen_latency is None else round(gen_latency, 4),
        'total_latency_s': '' if total_latency is None else round(total_latency, 4),
        'notes': _auto_note(ctx, abstained, primary, generated),
    }


def read_rows(csv_path=EVAL_CSV):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return []
    with csv_path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def append_row(row, csv_path=EVAL_CSV):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open('a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _run_specs(specs, csv_path, progress):
    """Run (kwargs) specs, skipping run_ids already in the CSV, appending each row at once."""
    done = {row['run_id'] for row in read_rows(csv_path)}
    new_rows = []
    for index, spec in enumerate(specs, start=1):
        run_id = make_run_id(spec['stage'], spec['dataset'], spec.get('variant', 'baseline'),
                             spec['model_info']['key'], spec['strategy'],
                             spec['query_item']['query_id'], spec.get('top_k', 3))
        if run_id in done:
            progress(f'[{index}/{len(specs)}] skip (already recorded): {run_id}')
            continue
        row = evaluate_one(**spec)
        append_row(row, csv_path)
        new_rows.append(row)
        progress(f'[{index}/{len(specs)}] {run_id}  context={row["context_score"]} '
                 f'answer={row["answer_score"]}')
    return new_rows


def run_main_grid(model_infos, chunks_by_strategy, embeddings, chunk_lookup, generation_info,
                  csv_path=EVAL_CSV, top_k=3, progress=print):
    """3 embedding models x 3 chunking strategies x 5 shared queries = 45 generation rows."""
    _require(generation_info is not None, 'main grid needs the locked generation model')
    specs = [dict(model_info=model_infos[key], strategy=strategy, query_item=item,
                  embeddings=embeddings, chunk_lookup=chunk_lookup,
                  generation_info=generation_info, stage='main', dataset='full',
                  top_k=top_k)
             for key in model_infos for strategy in chunks_by_strategy for item in TEST_QUERIES]
    _require(len(specs) == 45, f'expected 45 main-grid evaluations, got {len(specs)}')
    return _run_specs(specs, csv_path, progress)


def build_subset(records, ids=SCALING_SUBSET_IDS):
    """The 10-paragraph scaling subset, in knowledge-base order, plus its chunks."""
    wanted = set(ids)
    subset = [record for record in records if record['id'] in wanted]
    _require(len(subset) == len(ids), 'scaling subset ids not all found in the knowledge base')
    chunks = build_all_chunks(subset)
    return subset, chunks


def embed_subset(model_infos, subset_chunks):
    """Embed the subset chunks WITHOUT touching the committed full-dataset cache."""
    from embedding import embed_all_combinations
    return embed_all_combinations(model_infos, subset_chunks, use_cache=False)


def run_scaling_retrieval(model_infos, records, csv_path=EVAL_CSV, top_k=3, progress=print):
    """Retrieval-only rows (no generation) for all 45 configurations on the subset."""
    _, subset_chunks = build_subset(records)
    subset_embeddings = embed_subset(model_infos, subset_chunks)
    subset_lookup = build_chunk_lookup(subset_chunks)
    specs = [dict(model_info=model_infos[key], strategy=strategy, query_item=item,
                  embeddings=subset_embeddings, chunk_lookup=subset_lookup,
                  generation_info=None, stage='scaling', dataset='subset10', top_k=top_k)
             for key in model_infos for strategy in subset_chunks for item in TEST_QUERIES]
    return _run_specs(specs, csv_path, progress)


def run_scaling_generation(model_infos, records, generation_info, configs, csv_path=EVAL_CSV,
                           top_k=3, progress=print):
    """Full generation rows on the subset for chosen (model_key, strategy) configurations."""
    _, subset_chunks = build_subset(records)
    subset_embeddings = embed_subset(model_infos, subset_chunks)
    subset_lookup = build_chunk_lookup(subset_chunks)
    specs = [dict(model_info=model_infos[key], strategy=strategy, query_item=item,
                  embeddings=subset_embeddings, chunk_lookup=subset_lookup,
                  generation_info=generation_info, stage='scaling-gen', dataset='subset10',
                  top_k=top_k)
             for key, strategy in configs for item in TEST_QUERIES]
    return _run_specs(specs, csv_path, progress)


# Improvement variant (Part 3). Only the SYSTEM instruction text changes: the
# generation model, decoding settings, retrieval, Top-K, chunks, and queries are
# identical to the baseline run, so the before/after comparison isolates the prompt.
IMPROVEMENT_VARIANT = 'concise-complete'
PROMPT_VARIANTS = {
    IMPROVEMENT_VARIANT: (
        "You are the CozyDay planning assistant. Answer the user's question using only the "
        "retrieved context below. If the context does not contain enough information to answer "
        "confidently, say so explicitly instead of guessing. Ignore any context passage that "
        "does not help answer this question. Reply with a numbered list of at most five short "
        "steps, under 150 words in total, that covers every distinct recommendation in the "
        "relevant passages. Do not add examples or advice that are not in the context."
    ),
}
# Second attempt after the first variant lowered answer scores (see rag_analysis.md): keep the
# answer short enough to finish inside the locked 300-token limit, but do not force a terse
# list, so the context's own wording and the first recommended step survive.
SECOND_VARIANT = 'complete-within-limit'
PROMPT_VARIANTS[SECOND_VARIANT] = (
    "You are the CozyDay planning assistant. Answer the user's question using only the "
    "retrieved context below. If the context does not contain enough information to answer "
    "confidently, say so explicitly instead of guessing. Write a complete answer of at most "
    "170 words and finish every sentence. Use the context's own wording for each distinct "
    "recommendation that answers the question, begin with the first step the context "
    "recommends, and do not add examples or advice that are not in the context."
)


@contextlib.contextmanager
def prompt_variant(text):
    """Temporarily replace generation.SYSTEM_INSTRUCTION; always restored afterwards."""
    import generation
    original = generation.SYSTEM_INSTRUCTION
    generation.SYSTEM_INSTRUCTION = text
    try:
        yield
    finally:
        generation.SYSTEM_INSTRUCTION = original


def run_prompt_improvement(model_infos, chunks_by_strategy, embeddings, chunk_lookup,
                           generation_info, csv_path=EVAL_CSV, top_k=3, variant=IMPROVEMENT_VARIANT,
                           progress=print):
    """The same 45 evaluations as the main grid, with only the system prompt changed."""
    _require(generation_info is not None, 'improvement run needs the locked generation model')
    _require(variant in PROMPT_VARIANTS, f'unknown prompt variant {variant}')
    specs = [dict(model_info=model_infos[key], strategy=strategy, query_item=item,
                  embeddings=embeddings, chunk_lookup=chunk_lookup,
                  generation_info=generation_info, stage='improvement', dataset='full',
                  variant=variant, top_k=top_k)
             for key in model_infos for strategy in chunks_by_strategy for item in TEST_QUERIES]
    with prompt_variant(PROMPT_VARIANTS[variant]):
        return _run_specs(specs, csv_path, progress)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize(csv_path=EVAL_CSV, out_dir=RESULTS_DIR):
    """Write summary CSVs (embedding, chunking, configuration, query, scaling)."""
    import pandas as pd

    frame = pd.DataFrame(read_rows(csv_path))
    _require(not frame.empty, f'no rows in {csv_path}')
    for column in ['context_score', 'answer_score', 'evidence_recall', 'dimensions',
                   'embedding_latency_s', 'retrieval_latency_s', 'generation_latency_s',
                   'total_latency_s']:
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    main = frame[frame['stage'] == 'main']
    agg = dict(rows=('run_id', 'count'), mean_context_score=('context_score', 'mean'),
               mean_evidence_recall=('evidence_recall', 'mean'),
               mean_answer_score=('answer_score', 'mean'),
               mean_embedding_latency_s=('embedding_latency_s', 'mean'),
               mean_retrieval_latency_s=('retrieval_latency_s', 'mean'),
               mean_generation_latency_s=('generation_latency_s', 'mean'),
               mean_total_latency_s=('total_latency_s', 'mean'))
    written = {}
    if not main.empty:
        by_embedding = main.groupby(['embedding_key', 'dimensions']).agg(**agg).round(4)
        by_chunking = main.groupby('chunking').agg(**agg).round(4)
        by_config = main.groupby(['embedding_key', 'chunking']).agg(**agg).round(4)
        by_query = main.groupby('query_id').agg(**agg).round(4)
        for name, table in [('by_embedding', by_embedding), ('by_chunking', by_chunking),
                            ('by_configuration', by_config), ('by_query', by_query)]:
            path = out_dir / f'stage3_summary_{name}.csv'
            table.to_csv(path)
            written[name] = path

    sub = frame[(frame['dataset'] == 'subset10') & (frame['stage'] == 'scaling')]
    if not main.empty and not sub.empty:
        full_ret = main.groupby(['embedding_key', 'chunking']).agg(
            full_context=('context_score', 'mean'), full_recall=('evidence_recall', 'mean'))
        sub_ret = sub.groupby(['embedding_key', 'chunking']).agg(
            subset_context=('context_score', 'mean'), subset_recall=('evidence_recall', 'mean'))
        scaling = full_ret.join(sub_ret, how='inner')
        scaling['context_change_full_minus_subset'] = (
            scaling['full_context'] - scaling['subset_context'])
        path = out_dir / 'stage3_summary_scaling.csv'
        scaling.round(4).to_csv(path)
        written['scaling'] = path

        # Fair view: score only the expected evidence that actually exists in the subset,
        # so a paragraph that was removed from the data cannot count as a retrieval miss.
        expected = {q['query_id']: q['expected_evidence_ids'] for q in TEST_QUERIES}
        subset_ids = set(SCALING_SUBSET_IDS)

        def attainable_recall(row):
            reachable = [i for i in expected[row['query_id']] if i in subset_ids]
            got = set(str(row['retrieved_source_ids']).split(';'))
            return sum(1 for i in reachable if i in got) / len(reachable)

        both = pd.concat([main.assign(dataset_size='full_30'), sub.assign(dataset_size='subset_10')])
        both = both.assign(attainable_recall=both.apply(attainable_recall, axis=1))
        fair = both.pivot_table(index=['embedding_key', 'chunking'], columns='dataset_size',
                                values='attainable_recall', aggfunc='mean')
        fair['change_full_minus_subset'] = fair['full_30'] - fair['subset_10']
        path = out_dir / 'stage3_summary_scaling_attainable.csv'
        fair.round(4).to_csv(path)
        written['scaling_attainable'] = path

    improved = frame[frame['stage'] == 'improvement']
    if not main.empty and not improved.empty:
        import numpy as np
        before = main.assign(version='before_baseline_prompt')
        after = improved.assign(version='after_' + improved['variant'].astype(str))
        both = pd.concat([before, after])
        both['ends_cleanly'] = both['final_answer'].map(scoring.ends_cleanly).astype(float)
        both['answer_words'] = both['final_answer'].fillna('').str.split().str.len()
        cols = dict(rows=('run_id', 'count'), mean_context_score=('context_score', 'mean'),
                    mean_answer_score=('answer_score', 'mean'),
                    answers_ending_cleanly=('ends_cleanly', 'mean'),
                    mean_answer_words=('answer_words', 'mean'),
                    mean_generation_latency_s=('generation_latency_s', 'mean'))
        for name, keys in [('overall', ['version']), ('by_query', ['version', 'query_id']),
                           ('by_chunking', ['version', 'chunking']),
                           ('by_embedding', ['version', 'embedding_key'])]:
            path = out_dir / f'stage3_improvement_{name}.csv'
            both.groupby(keys).agg(**cols).round(4).to_csv(path)
            written[f'improvement_{name}'] = path
    return written


def _load_everything(need_generation):
    from embedding import embed_all_combinations, load_all_embedding_models
    records = load_knowledge_base()
    chunks_by_strategy = build_all_chunks(records)
    model_infos = load_all_embedding_models()
    embeddings = embed_all_combinations(model_infos, chunks_by_strategy)
    chunk_lookup = build_chunk_lookup(chunks_by_strategy)
    generation_info = None
    if need_generation:
        from generation import load_generation_model
        generation_info = load_generation_model()
    return records, chunks_by_strategy, model_infos, embeddings, chunk_lookup, generation_info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=['main', 'scaling-retrieval', 'scaling-generation',
                                            'improve-prompt', 'summary'])
    parser.add_argument('--model', choices=['small', 'medium', 'large'])
    parser.add_argument('--strategy', choices=['fixed', 'overlap', 'hybrid'])
    parser.add_argument('--variant', choices=sorted(PROMPT_VARIANTS), default=IMPROVEMENT_VARIANT,
                        help='prompt variant for improve-prompt')
    args = parser.parse_args(argv)

    if args.command == 'summary':
        for name, path in summarize().items():
            print(f'wrote {name}: {path}')
        return 0
    if args.command in ('main', 'improve-prompt'):
        (_, chunks_by_strategy, model_infos, embeddings, chunk_lookup,
         generation_info) = _load_everything(need_generation=True)
        if args.command == 'main':
            run_main_grid(model_infos, chunks_by_strategy, embeddings, chunk_lookup, generation_info)
        else:
            run_prompt_improvement(model_infos, chunks_by_strategy, embeddings, chunk_lookup,
                                   generation_info, variant=args.variant)
        return 0
    if args.command == 'scaling-retrieval':
        records, _, model_infos, _, _, _ = _load_everything(need_generation=False)
        run_scaling_retrieval(model_infos, records)
        return 0
    _require(args.model and args.strategy, 'scaling-generation needs --model and --strategy')
    records, _, model_infos, _, _, generation_info = _load_everything(need_generation=True)
    run_scaling_generation(model_infos, records, generation_info, [(args.model, args.strategy)])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
