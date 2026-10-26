"""Exact NF4 loading configuration for the two Stage 3 runs that differ from the shared loader.

The shared ``a7_shared.load_model`` loads 4-bit NF4 models with an fp16 compute dtype and
fp16 non-quantized layers, and ``a7_shared.protocol_id`` hashes ``nf4_compute: fp16``.
Qwen2.5-7B produced corrupted output under that configuration, so Models 14 and 15 were
run with the settings in ``NF4_RUNS`` below. This module is the committed, single source of
truth for those settings: it holds the loader, the matching protocol ID and the metadata
that is saved into the result CSVs. ``a7_shared.py`` itself is unchanged.

Importing this module never imports torch or transformers; only ``load_model_nf4`` does.

Re-running a model (needs the GPU, ~15 GB; one model per process), from the repo root:
    python llm-test/a7_stage3_nf4.py 14
    python llm-test/a7_stage3_nf4.py 15
Completed 25-row result files are never overwritten: ``run_models`` returns them unchanged.
"""
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))
import a7_shared as shared

LOADER = "llm-test/a7_stage3_nf4.py"
TORCH_NAMES = {"fp16": "float16", "fp32": "float32", "bf16": "bfloat16"}

# Everything else is identical to the shared CUDA NF4 branch: device_map={"": 0}, eager
# attention, trust_remote_code=False, load_in_4bit, bnb_4bit_quant_type="nf4" and
# bnb_4bit_use_double_quant=True. "torch_dtype" is the dtype of the non-quantized layers
# (embeddings, norms, lm_head); the shared loader uses float16 for them.
NF4_RUNS = {
    14: {"model": "Qwen/Qwen2.5-7B-Instruct", "backend": "cuda", "precision": "nf4",
         "compute_dtype": "fp32", "torch_dtype": "float32"},
    15: {"model": "Qwen/Qwen2.5-14B-Instruct", "backend": "cuda", "precision": "nf4",
         "compute_dtype": "bf16", "torch_dtype": "bfloat16"},
}


def protocol_id_nf4(model_id, prompts, backend, precision, compute_dtype):
    """Same hash as ``shared.protocol_id`` with the real NF4 compute dtype."""
    if compute_dtype not in TORCH_NAMES:
        raise ValueError("compute_dtype must be fp16, fp32 or bf16")
    config = {"model": model_id, "prompts": prompts.to_dict("records"), "system": shared.SYSTEM,
              "backend": backend, "precision": shared.normalize_precision(precision),
              "max_new_tokens": shared.MAX_NEW_TOKENS, "do_sample": False,
              "qwen3_thinking": False, "gemma2_system_in_user": True,
              "nf4_double_quant": True, "nf4_compute": compute_dtype}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def load_model_nf4(model_id, *, compute_dtype, torch_dtype, local_only=False):
    """CUDA NF4 loader identical to the shared one except for the two dtypes."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable")
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=local_only,
                                              trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, local_files_only=local_only, trust_remote_code=False,
        device_map={"": 0}, attn_implementation="eager",
        torch_dtype=getattr(torch, TORCH_NAMES.get(torch_dtype, torch_dtype)),
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=getattr(torch, TORCH_NAMES[compute_dtype]),
            bnb_4bit_use_double_quant=True))
    model.eval()
    return tokenizer, model


def runtime_with_loader(runtime_json, number):
    """Add the real NF4 settings to a saved Runtime JSON string (idempotent)."""
    run = NF4_RUNS[number]
    runtime = json.loads(runtime_json)
    runtime.update({"nf4_compute": run["compute_dtype"], "torch_dtype": run["torch_dtype"],
                    "loader": LOADER})
    return json.dumps(runtime)


def annotate_results(prompts, result_dir):
    """Write the correct Protocol ID and loader settings into the Model 14/15 CSVs.

    Only the ``Protocol ID`` and ``Runtime`` columns change. Used once to correct the
    saved Stage 3 files and by the runner after a new run; safe to repeat.
    """
    result_dir = Path(result_dir)
    for number, run in NF4_RUNS.items():
        pid = protocol_id_nf4(run["model"], prompts, run["backend"], run["precision"],
                              run["compute_dtype"])
        for name in (f"a7_model_{number}_benchmark.csv", f"a7_model_{number}_scored.csv"):
            path = result_dir / name
            if not path.exists():
                continue
            frame = pd.read_csv(path)
            frame["Protocol ID"] = pid
            frame["Runtime"] = frame["Runtime"].map(lambda r: runtime_with_loader(r, number))
            frame.to_csv(path, index=False, lineterminator="\n")
    combined = result_dir / "a7_stage3_all_benchmarks.csv"
    if combined.exists():
        frame = pd.read_csv(combined)
        for number, run in NF4_RUNS.items():
            rows = frame["Model No."] == number
            if rows.any():
                frame.loc[rows, "Protocol ID"] = protocol_id_nf4(
                    run["model"], prompts, run["backend"], run["precision"], run["compute_dtype"])
                frame.loc[rows, "Runtime"] = frame.loc[rows, "Runtime"].map(
                    lambda r, n=number: runtime_with_loader(r, n))
        frame.to_csv(combined, index=False, lineterminator="\n")


def load_prompts():
    notebook = json.loads((MODULE_DIR / "multi_model_system.ipynb").read_text(encoding="utf-8"))
    cell = next(c for c in notebook["cells"]
                if c["cell_type"] == "code" and "evaluation_prompts" in "".join(c["source"]))
    namespace = {"display": lambda *a, **k: None, "validate_prompts": lambda df: None}
    exec("".join(cell["source"]).replace("validate_prompts(prompts_df)", ""), namespace)
    prompts = namespace["prompts_df"]
    shared.validate_prompts(prompts)
    return prompts


def main(number):
    run = NF4_RUNS[number]
    prompts = load_prompts()
    results = MODULE_DIR / "results"
    matrix = pd.read_csv(results / "research_matrix.csv")
    original_loader, original_protocol = shared.load_model, shared.protocol_id
    shared.load_model = lambda model_id, *, backend, precision, local_only=False: load_model_nf4(
        model_id, compute_dtype=run["compute_dtype"], torch_dtype=run["torch_dtype"],
        local_only=local_only)
    shared.protocol_id = lambda model_id, prompts_df, backend, precision: protocol_id_nf4(
        model_id, prompts_df, backend, precision, run["compute_dtype"])
    try:
        data = shared.run_models([number], matrix, prompts, results, execute=True,
                                 backend=run["backend"], precision=run["precision"])[number]
    finally:
        shared.load_model, shared.protocol_id = original_loader, original_protocol
    annotate_results(prompts, results)
    print("Rows:", len(data), "| mean latency:", round(data["Latency"].mean(), 2),
          "| cap hits:", int(data["Reached Token Limit"].sum()))


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) not in NF4_RUNS:
        sys.exit("usage: python llm-test/a7_stage3_nf4.py 14|15")
    main(int(sys.argv[1]))
