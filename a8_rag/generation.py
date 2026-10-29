"""CozyDay Stage 2: locked generation pipeline.

Reuses Qwen/Qwen2.5-3B-Instruct, previously evaluated as Model 9 in the A7
multi-model assignment, per the team's shared contract recommendation. The
model name and decoding settings below never change between experiments;
Stage 3/4 must reuse this module rather than re-deriving settings.
"""
from __future__ import annotations

import time

GENERATION_MODEL = 'Qwen/Qwen2.5-3B-Instruct'
# Locked, deterministic (greedy) decoding settings; identical for every
# experiment in this assignment, including all nine Stage 2 smoke tests.
DECODING_SETTINGS = {
    'max_new_tokens': 300,
    'do_sample': False,
    'num_beams': 1,
}
SYSTEM_INSTRUCTION = (
    "You are the CozyDay planning assistant. Answer the user's question using only the "
    "retrieved context below. If the context does not contain enough information to answer "
    "confidently, say so explicitly instead of guessing."
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def load_generation_model(device=None):
    """Load the locked generation model/tokenizer once; reused by every run_rag call."""
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from embedding import pick_device
    resolved_device = pick_device(device)
    start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(GENERATION_MODEL)
    model = AutoModelForCausalLM.from_pretrained(GENERATION_MODEL)
    model.to(resolved_device)
    load_time = time.perf_counter() - start
    return {'model_name': GENERATION_MODEL, 'model': model, 'tokenizer': tokenizer,
            'device': resolved_device, 'load_time_seconds': load_time}


def describe_generation_model(generation_info):
    """Flat {model_name, device, load_time_seconds, decoding_settings} for display."""
    return {'model_name': generation_info['model_name'], 'device': generation_info['device'],
            'load_time_seconds': generation_info['load_time_seconds'],
            'decoding_settings': dict(DECODING_SETTINGS)}


def build_prompt(context_chunks, query):
    """System instruction + retrieved context + user query, as chat messages.

    The system instruction explicitly tells the model to rely on context and
    to acknowledge insufficient evidence rather than guess.
    """
    _require(isinstance(context_chunks, list), 'context_chunks must be a list')
    _require(isinstance(query, str) and query.strip(), 'query must be a nonempty string')
    context_text = '\n\n'.join(
        f"[{chunk['chunk_id']}] {chunk['text']}" for chunk in context_chunks
    ) if context_chunks else '(no context retrieved)'
    user_content = f"Context:\n{context_text}\n\nQuestion: {query}"
    return [
        {'role': 'system', 'content': SYSTEM_INSTRUCTION},
        {'role': 'user', 'content': user_content},
    ]


def generate_answer(generation_info, context_chunks, query):
    """Run the locked generation model on one (context, query) pair.

    Returns (answer_text, latency_seconds). Decoding settings never change
    between calls; see DECODING_SETTINGS.
    """
    model = generation_info['model']
    tokenizer = generation_info['tokenizer']
    messages = build_prompt(context_chunks, query)
    prompt_text = tokenizer.apply_chat_template(messages, tokenize=False,
                                                 add_generation_prompt=True)
    inputs = tokenizer(prompt_text, return_tensors='pt').to(generation_info['device'])

    start = time.perf_counter()
    output_ids = model.generate(
        **inputs,
        max_new_tokens=DECODING_SETTINGS['max_new_tokens'],
        do_sample=DECODING_SETTINGS['do_sample'],
        num_beams=DECODING_SETTINGS['num_beams'],
    )
    latency = time.perf_counter() - start

    generated = output_ids[0][inputs['input_ids'].shape[1]:]
    answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
    return answer, latency
