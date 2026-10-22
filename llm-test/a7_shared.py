"""A7 shared helpers. Importing or using execute=False never loads model libraries."""
import gc
import hashlib
import json
import math
import platform
import sys
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

SYSTEM = ("You are CozyDay, a helpful daily planning assistant. "
          "Use only the information given by the user. "
          "Follow the requested format. Be accurate and concise.")
TRAFFIC = {"Prototype": 1000, "Early Startup": 10000, "Growing Product": 100000,
           "Large Platform": 1000000, "Mass Consumer App": 10000000,
           "Global Platform": 100000000}
MAX_NEW_TOKENS = 256
SCORE_COLUMNS = ["Instruction Adherence", "Accuracy", "Clarity", "Structure"]


def registry(matrix):
    if len(matrix) != 15 or matrix["Model No."].duplicated().any():
        raise ValueError("Expected exactly 15 distinct model records")
    models = {int(r["Model No."]): (r["Model Name"], r["Category"])
              for _, r in matrix.iterrows()}
    if set(models) != set(range(1, 16)):
        raise ValueError("Expected model numbers 1–15")
    return models


def normalize_precision(value):
    aliases = {"float32": "float32", "torch.float32": "float32", "fp32": "float32",
               "bfloat16": "bfloat16", "torch.bfloat16": "bfloat16", "bf16": "bfloat16",
               "float16": "fp16", "torch.float16": "fp16", "fp16": "fp16",
               "4-bit nf4": "nf4", "nf4": "nf4"}
    try:
        return aliases[str(value).strip().lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported precision: {value}") from exc


def prepare_messages(model_id, prompt):
    """Gemma 2 rejects system turns; preserve the exact prompt inside its user wrapper."""
    if model_id.startswith("google/gemma-2-"):
        return [{"role": "user", "content": SYSTEM + "\n\n" + prompt}]
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]


def validate_prompts(prompts):
    if (len(prompts) != 25 or not prompts["Prompt ID"].is_unique
            or prompts["Prompt Type"].nunique() != 5
            or not prompts["Prompt Type"].value_counts().eq(5).all()
            or prompts[["Prompt ID", "Prompt Type", "Prompt"]].isna().any().any()):
        raise ValueError("Expected 25 unique prompts, five in each of five types")


def protocol_id(model_id, prompts, backend, precision):
    config = {"model": model_id, "prompts": prompts.to_dict("records"), "system": SYSTEM,
              "backend": backend, "precision": normalize_precision(precision),
              "max_new_tokens": MAX_NEW_TOKENS, "do_sample": False,
              "qwen3_thinking": False, "gemma2_system_in_user": True,
              "nf4_double_quant": True, "nf4_compute": "fp16"}
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def validate_records(frame, model_id, category, prompts):
    """Validate measurements without changing historical CSV representations."""
    required = {"Prompt ID", "Prompt", "Prompt Type", "Model", "Model Category",
                "Max New Tokens", "Response", "Latency", "Tokens/sec", "Generated Tokens",
                "Precision", "Backend", "Device", "Reached Token Limit"}
    if not required.issubset(frame.columns) or frame["Prompt ID"].duplicated().any():
        raise ValueError("Invalid benchmark columns or duplicate prompt IDs")
    if frame[list(required)].isna().any().any():
        raise ValueError("Missing benchmark values")
    reference = prompts.set_index("Prompt ID")
    for _, row in frame.iterrows():
        if row["Prompt ID"] not in reference.index:
            raise ValueError("Unexpected prompt ID")
        expected = reference.loc[row["Prompt ID"]]
        if (row["Prompt"] != expected["Prompt"] or row["Prompt Type"] != expected["Prompt Type"]
                or row["Model"] != model_id or row["Model Category"] != category
                or row["Max New Tokens"] != MAX_NEW_TOKENS):
            raise ValueError("Benchmark model, prompt or generation configuration mismatch")
        if not str(row["Response"]).strip():
            raise ValueError("Empty model response")
        latency, speed, tokens = (float(row[k]) for k in ("Latency", "Tokens/sec", "Generated Tokens"))
        if (not all(math.isfinite(x) and x > 0 for x in (latency, speed, tokens))
                or tokens != int(tokens) or tokens > MAX_NEW_TOKENS):
            raise ValueError("Invalid timing or token measurement")
        # Both elapsed seconds and throughput were stored to three decimals.
        tolerance = tokens * 0.000501 / (latency * max(latency - 0.000501, 1e-9)) + 0.000501
        if abs(tokens / latency - speed) > tolerance:
            raise ValueError("Tokens/sec disagrees with token count and latency")
        limit = str(row["Reached Token Limit"]).lower()
        if limit not in ("true", "false") or (limit == "true") != (tokens == MAX_NEW_TOKENS):
            raise ValueError("Invalid token-limit flag")
        normalize_precision(row["Precision"])


def load_model(model_id, *, backend="cpu", precision="float32", local_only=False):
    precision = normalize_precision(precision)
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=local_only,
                                              trust_remote_code=False)
    kwargs = {"local_files_only": local_only, "trust_remote_code": False}
    if backend == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU unavailable")
        kwargs.update(device_map={"": 0}, attn_implementation="eager", torch_dtype=torch.float16)
        if precision == "nf4":
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        elif precision != "fp16":
            raise ValueError("GPU precision must be fp16 or nf4")
    elif backend == "cpu" and precision in ("float32", "bfloat16"):
        kwargs["torch_dtype"] = torch.float32 if precision == "float32" else torch.bfloat16
    else:
        raise ValueError("Use cpu with float32/bfloat16 or cuda with fp16/nf4")
    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    model.eval()
    return tokenizer, model


def run_models(numbers, model_matrix, prompts_df, result_dir, *, execute=False,
               backend="cpu", precision="float32", local_only=False):
    """Opt-in inference. Completed historical files are read without loading weights.

    Partial files require this helper's protocol ID; legacy partial runs must use a
    fresh directory, never silently mix historical and new experiments.
    """
    models = registry(model_matrix)
    validate_prompts(prompts_df)
    if not execute:
        return {}
    precision = normalize_precision(precision)
    if (backend, precision) not in {("cpu", "float32"), ("cpu", "bfloat16"),
                                    ("cuda", "fp16"), ("cuda", "nf4")}:
        raise ValueError("Unsupported backend/precision pair")
    result_dir = Path(result_dir)
    output = {}
    for number in numbers:
        model_id, category = models[number]
        path = result_dir / f"a7_model_{number}_benchmark.csv"
        previous = pd.read_csv(path) if path.exists() else pd.DataFrame()
        run_id = protocol_id(model_id, prompts_df, backend, precision)
        if path.exists():
            validate_records(previous, model_id, category, prompts_df)
        if len(previous) == 25:
            output[number] = previous
            continue  # Existing measurements are authoritative; no writes or model imports.
        if not previous.empty:
            if ("Protocol ID" not in previous or not previous["Protocol ID"].eq(run_id).all()
                    or not previous["Precision"].map(normalize_precision).eq(precision).all()
                    or not previous["Device"].str.split(":").str[0].eq(backend).all()):
                raise ValueError("Partial resume configuration mismatch; use a fresh directory")
        import torch
        runtime = json.dumps({"python": sys.version, "platform": platform.platform(),
                              "cpu": platform.processor(), "torch": torch.__version__,
                              "gpu": torch.cuda.get_device_name(0) if backend == "cuda" else None,
                              "cpu_threads": torch.get_num_threads()}, sort_keys=True)
        if not previous.empty and ("Runtime" not in previous or not previous["Runtime"].eq(runtime).all()):
            raise ValueError("Partial resume hardware/software mismatch; use a fresh directory")
        result_dir.mkdir(parents=True, exist_ok=True)
        rows = previous.to_dict("records")
        completed = set(previous["Prompt ID"]) if not previous.empty else set()
        tokenizer, model = load_model(model_id, backend=backend, precision=precision,
                                      local_only=local_only)
        device = next(model.parameters()).device
        try:
            for _, item in prompts_df.iterrows():
                if item["Prompt ID"] in completed:
                    continue
                options = {"enable_thinking": False} if "Qwen3" in model_id else {}
                inputs = tokenizer.apply_chat_template(
                    prepare_messages(model_id, item["Prompt"]), tokenize=True,
                    add_generation_prompt=True, return_tensors="pt", return_dict=True, **options)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                if device.type == "cuda":
                    torch.cuda.synchronize()
                start = time.perf_counter()
                with torch.inference_mode():
                    generated = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS,
                                               do_sample=False, pad_token_id=tokenizer.eos_token_id)
                if device.type == "cuda":
                    torch.cuda.synchronize()
                elapsed = time.perf_counter() - start
                new = generated[0][inputs["input_ids"].shape[-1]:]
                count = len(new)
                row = {"Model": model_id, "Model Category": category,
                       "Tokens/sec": round(count / elapsed, 3), "Latency": round(elapsed, 3),
                       "Prompt Type": item["Prompt Type"], "Prompt": item["Prompt"],
                       "Self-Evaluation Score (1-10)": None, "Prompt ID": item["Prompt ID"],
                       "Response": tokenizer.decode(new, skip_special_tokens=True),
                       "Generated Tokens": count, "Reached Token Limit": count >= MAX_NEW_TOKENS,
                       "Backend": "Transformers", "Device": str(device), "Precision": precision,
                       "Max New Tokens": MAX_NEW_TOKENS, "Protocol ID": run_id, "Runtime": runtime}
                row.update({key: None for key in SCORE_COLUMNS})
                rows.append(row)
                current = pd.DataFrame(rows)
                validate_records(current, model_id, category, prompts_df)
                tmp = path.with_suffix(".tmp")
                current.to_csv(tmp, index=False)
                tmp.replace(path)
            output[number] = pd.DataFrame(rows)
        finally:
            del model, tokenizer
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
    return output


def money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_costs(numbers, model_matrix, throughput, api_models, *, input_tokens=250,
                    output_tokens=500, requests_per_user=1, utilization=.7,
                    machine_hourly=1.006, days=30, gateway_hourly=.05, gateway_rps=100):
    """Six local and six sourced API rows/model; rates are USD per million tokens.

    api_models[number] requires model, provider, input_usd_per_million,
    output_usd_per_million, source_url, checked_date and comparison_note.
    No files are written. Callers choose their own output directory explicitly.
    """
    numeric = [input_tokens, output_tokens, requests_per_user, utilization,
               machine_hourly, days, gateway_hourly, gateway_rps]
    if not all(math.isfinite(float(x)) and float(x) > 0 for x in numeric) or utilization > 1:
        raise ValueError("Cost assumptions must be positive finite numbers; utilization <= 1")
    models = registry(model_matrix)
    local, api = [], []
    required = {"model", "provider", "input_usd_per_million", "output_usd_per_million",
                "source_url", "checked_date", "comparison_note"}
    for number in numbers:
        mid, _ = models[number]
        tps, quote = throughput[number], api_models[number]
        if not math.isfinite(float(tps)) or tps <= 0 or not required.issubset(quote):
            raise ValueError("Missing price metadata or invalid cloud throughput")
        rates = [quote["input_usd_per_million"], quote["output_usd_per_million"]]
        if not all(math.isfinite(float(x)) and float(x) >= 0 for x in rates):
            raise ValueError("Invalid input/output prices")
        if any(not str(quote[k]).strip() for k in required) or not quote["source_url"].startswith("https://"):
            raise ValueError("Price metadata must be nonempty and sourced")
        for group, dau in TRAFFIC.items():
            requests = dau * requests_per_user
            tokens = requests * output_tokens
            daily_input = requests * input_tokens
            machines = max(1, math.ceil(tokens / (tps * 86400 * utilization)))
            gateways = max(1, math.ceil(requests / (86400 * gateway_rps)))
            local_month = money(machines * machine_hourly * 24 * days)
            # Decimal avoids binary half-cent ambiguity. Round provider bill once.
            provider_bill = (Decimal(str(daily_input)) * Decimal(str(rates[0]))
                             + Decimal(str(tokens)) * Decimal(str(rates[1]))) * Decimal(str(days)) / Decimal(1000000)
            api_month = money(provider_bill)
            gateway_month = money(gateways * gateway_hourly * 24 * days)
            local.append({"Model Name": mid, "Daily Traffic Category": group,
                          "Daily Active Users": dau, "Avg Tokens per User": output_tokens,
                          "Total Daily Token Load": tokens, "Per Machine Cost (Cloud)": machine_hourly,
                          "Machines Needed": machines, "Total Machine Cost": local_month,
                          "Cloud Throughput Assumption (tokens/sec)": tps, "Cost Period": "USD/month"})
            api.append({"Local LLM Model Size": mid,
                        "Comparable Paid Model Hosted on Hugging Face": quote["model"],
                        "Output USD per Token": rates[1] / 1e6,
                        "Daily Traffic Category": group, "Total Token Load": tokens,
                        "Estimated API Cost": api_month,
                        "Machines Required (API infrastructure)": gateways,
                        "Total Cost": money(Decimal(str(api_month)) + Decimal(str(gateway_month))),
                        "API Gateway Cost": gateway_month,
                        "Pricing Status": "Verified HF listing; workload and gateway are assumptions",
                        "Cost Period": "USD/month", "Paid Provider": quote["provider"],
                        "Input USD per 1M tokens": rates[0], "Output USD per 1M tokens": rates[1],
                        "Assumed Input Tokens per Request": input_tokens,
                        "Assumed Output Tokens per Request": output_tokens,
                        "Total Daily Input Tokens": daily_input,
                        "Model Comparison Note": quote["comparison_note"],
                        "Price Source URL": quote["source_url"],
                        "Price Checked Date": quote["checked_date"]})
    return pd.DataFrame(local), pd.DataFrame(api)
