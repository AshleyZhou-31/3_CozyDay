# CozyDay Multi Model AI System

## Stage 1 scope and evidence

Lin supplies the shared 15-model registry, unchanged 25-prompt protocol, Models 1–5 experiments and scores, and 30 local plus 30 paid API cost scenarios. Stages 2 and 3 own the remaining models and their routing sections; Ashley owns final cross-model conclusions, architecture switching analysis, integration and remaining routes. Those experiments and final conclusions are intentionally not supplied here.

The five categories contain three models each and use the unchanged nominal A6 parameter labels, not exact tensor parameter counts. Prompt types are Task Classification, Priority Ranking, Schedule Generation, Plan Summarization and Structured Extraction, with five prompts each.

## Benchmark results

| Model | Mean score | Mean latency seconds | Mean output tokens per second | Token cap hits |
|---|---:|---:|---:|---:|
| SmolLM2-135M | 2.76 | 5.19 | 24.49 | 10 |
| Qwen2.5-0.5B | 6.76 | 5.56 | 12.37 | 1 |
| Qwen3-1.7B | 7.96 | 17.34 | 4.34 | 2 |
| Phi-3.5-mini | 9.40 | 6.05 | 24.21 | 3 |
| Qwen3-8B | 9.60 | 6.66 | 11.76 | 1 |

Each model has 25 scored records. Raw response texts, generated-token counts, latencies and throughput are preserved exactly from the original Stage 1 experiments. The combined and summary CSVs retain the reviewed scores. These are single-run measurements, not estimates with confidence intervals. Low-quality or truncated responses remain legitimate measured records and are scored accordingly.

Latency measures the generate call, excluding loading, input preparation and text decoding. Throughput is generated token IDs divided by generation seconds, including generated special tokens; both reported timing fields are rounded to three decimals. The summary averages per-request rates, rather than dividing aggregate tokens by aggregate time. Output length varies by model, so request latency is also sensitive to response verbosity.

### Hardware and reproducibility limits

Models 1–3 used local CPU with bfloat16 metadata. Model 4 used Colab Tesla T4 FP16, native Phi implementation and eager attention. Model 5 used Colab T4 with NF4, double quantization and FP16 compute; Qwen3 thinking was disabled. Colab GPU memory was reported as 14.56 GB. The experiment author reported CUDA synchronization around generation; original GPU execution logs are not committed, so this historical detail is not independently authenticated here.

Previously reported environments: Colab Python 3.13.15, torch 2.11.0+cu130, Transformers 5.20.1, accelerate 1.15.0 and bitsandbytes 0.50.2; local torch 2.14.1+cpu and Transformers 5.19.0. These are historical reports, not a promise that every version is available or installable on another system. Exact model revisions, CPU model, RAM and CPU thread settings were not captured. No standardized warm-up or identical-hardware rerun was conducted. Speed differences cannot be attributed solely to model size, and NF4 quality is not identical to full-precision quality.

The repaired helper explicitly selects CPU float32/bfloat16 or CUDA FP16/NF4 and synchronizes future GPU timings. It does not retroactively change measurements or fill missing historical metadata. No model inference or weight download was performed during this correction.

## Evaluation rubric and calibration

Instruction adherence, accuracy, clarity and structure each receive an integer from 1–10 and equal 25% weight. Their mean is rounded half up: floor(mean + 0.5). Bands are 1–2 very poor, 3–4 poor, 5–6 acceptable, 7–8 good and 9–10 excellent. Scores are subjective manual evaluations of saved outputs, not independently calibrated quality estimates.

Classification should cover all supplied tasks; C2–C4 permit meaningful alternative category labels. Priority ranking should respect explicit deadlines and avoid inventing urgency. Schedules should satisfy durations without collisions. Summaries should preserve facts and obey requested sentence count. Extraction should include requested tasks without inventions; JSON inside Markdown fences is accepted if the contents parse. Missing/truncated content reduces adherence or structure. Failed inference is reported as a failure, never filled with fabricated measurements or scores.

| Reviewed record | Adherence | Accuracy | Clarity | Structure | Overall | Reason |
|---|---:|---:|---:|---:|---:|---|
| Model 2 P5 | 8 | 7 | 9 | 9 | 8 | Desk precedes quiz without justification; calibrated consistently with Model 5 |
| Model 3 M4 | 7 | 9 | 10 | 7 | 8 | One sentence instead of the requested two |
| Model 4 S5 | 9 | 6 | 9 | 10 | 9 | Four scheduled hours leave two spare hours, not the claimed one; mean 8.5 rounds to 9 |
| Model 5 S1 | 7 | 10 | 9 | 6 | 8 | Correct requested durations, but response ends mid-item at the 256-token cap |

These adjustments are complete. No further scoring change is included in this correction.

## Shared traffic and local hosting estimates

The prospective planning workload is 250 input plus 500 generated tokens per request, one request per daily active user per day and 30 days per month. The 500-token output is a stress-planning assumption, not the measured output average or a change to the 256-token benchmark limit. All stages should retain these shared workload conventions or explicitly add a separately labeled sensitivity scenario.

Daily users are 1,000; 10,000; 100,000; 1,000,000; 10,000,000; and 100,000,000. Daily output tokens = DAU × requests/user/day × output tokens/request. Daily input tokens use the same formula with input tokens/request.

The reference machine is AWS g5.xlarge with NVIDIA A10G 24 GB. USD 1.006/hour is retained as an **unverified planning assumption**, not a newly sourced current quote. Assumed output throughput for Models 1–5 is 60, 45, 30, 20 and 12 tokens/second at 70% utilization. These are capacity assumptions, not measured A10G results. Quantization, memory headroom, CPU/RAM specifications and actual throughput must be checked before provisioning.

- Daily machine capacity = assumed output tokens/second × 86,400 × utilization.
- Machines needed = ceiling(daily output tokens / daily machine capacity).
- Monthly local cost = machines × hourly machine price × 24 × 30.

All 30 local rows are unchanged. Their historical `Per Machine Cost (Cloud)` field is USD/hour; `Total Machine Cost` is USD/month. Input prefill overhead is implicit in the assumed throughput, not separately benchmarked or billed. Relevant reference pages: https://aws.amazon.com/ec2/instance-types/g5/ and https://aws.amazon.com/ec2/pricing/on-demand/ (reference URLs recorded 2026-10-21; the assumed price is not independently verified).

## Paid Hugging Face provider comparison

Verified on 2026-10-21 against the official [HF provider price listing](https://huggingface.co/inference/models), [Nscale integration](https://huggingface.co/docs/inference-providers/providers/nscale) and [Nscale-supported models](https://huggingface.co/models?inference_provider=nscale&sort=trending). Listing snapshots and per-local-model metadata live in `llm-test/a7_api_pricing.json`. Prices are USD per million tokens and can change; no paid API request was made. The previous unsupported DeepSeek-1.5B/nscale pairing and hypothetical prices are not used.

| Local model | Paid model and provider | Input USD per million | Output USD per million | Comparability limitation |
|---|---|---:|---:|---|
| SmolLM2-135M | Qwen/Qwen3-4B-Instruct-2507, nscale | 0.01 | 0.03 | Task-based instruct proxy, about 30 times larger; not a Tiny-model quote |
| Qwen2.5-0.5B | Qwen/Qwen3-4B-Instruct-2507, nscale | 0.01 | 0.03 | Task-based proxy, about 8 times larger |
| Qwen3-1.7B | Qwen/Qwen3-4B-Instruct-2507, nscale | 0.01 | 0.03 | Task-based proxy, about 2.4 times larger and different training |
| Phi-3.5-mini 3.8B | Qwen/Qwen3-4B-Instruct-2507, nscale | 0.01 | 0.03 | Similar nominal size, different model family |
| Qwen3-8B | Qwen/Qwen3-8B, nscale | 0.07 | 0.18 | Same model ID, but hosted precision/thinking settings unverified versus local NF4 non-thinking |

The paid instruct model is a plausible substitute for classification, scheduling, summarization and extraction tasks. Its task quality has not been benchmarked here. Reusing one task-based proxy for multiple local models is intentional; costs are not claimed to imply equivalent quality or equal parameter sizes. All six previously unavailable Tiny rows now have explicit larger-model proxy costs, not invented Tiny-model prices.

Monthly provider cost = 30 × (daily input tokens × input USD/million + daily output tokens × output USD/million) / 1,000,000.

Assumed client-side API gateway price is USD 0.05/hour with capacity 100 requests/second. Gateway count = ceiling(daily requests / (86,400 × 100)), minimum one. Monthly gateway cost = count × 0.05 × 24 × 30. These are planning assumptions, not provider quotes or counts of the provider's inference GPUs. Both provider and gateway bills are rounded half up to cents before summing total monthly cost. Example: the 4B proxy at 1,000 DAU costs 0.525 unrounded provider dollars, rounded to 0.53; total including the 36.00 gateway is 36.53.

`llm-test/results/a7_stage1_api_cost.csv` contains 30 complete rows. Daily output load is `Total Token Load`; input load is `Total Daily Input Tokens`. API and total cost are USD/month. Both input and output charges are included. `Output USD per Token` represents output price only. The shared cost function reproduces both cost CSVs; notebook Run All recomputes them in memory and checks equality without overwriting them.

### Cost limitations

Estimates exclude storage, transfer, redundancy, labor, taxes, discounts, subscription credits, quotas, peak queues and provider capacity reservations. Average-load machine counts are not peak-load service guarantees. Cloud throughput, gateway economics and proxy output lengths are assumptions, not production measurements. Provider quality, hosted precision and thinking behavior may differ; a real architecture decision requires task-quality and capacity checks. Final scale-switching conclusions belong to Ashley's all-model analysis.

## Peak Usage Hours routing scenario

Stage 2 adds one routing scenario, Peak Usage Hours, covering trigger condition, local and API model choice, fallback behavior, expected benefit, and a latency/cost/quality evaluation kept as three separate axes rather than one blended score. It uses Model 8 (`google/gemma-2-2b-it`, Medium) and Model 10 (`mistralai/Mistral-Nemo-Instruct-2407`, Very Large, NF4) from Rishabh's Stage 2 slot as the local-side examples, reusing the shared traffic tiers, throughput assumptions and cost-model contract from the "Shared traffic and local hosting estimates" section above rather than introducing new ones, except for one explicitly labeled addition below.

### Trigger

The shared cost model sizes a fleet for each tier's daily-average output rate; it does not model intra-day peaks. This scenario adds one new, explicitly labeled **planning assumption**, not a measured value: peak hours carry 3x the day's uniform-average output rate for 4 hours/day. At the 100,000 DAU tier (250 input / 500 output tokens/request, the shared convention), the uniform-average rate is 578.70 output tokens/second; the assumed peak rate is 1,736.11 tokens/second.

Using the Very Large category's assumed 12 tokens/second/machine at 70% utilization (effective 8.4 tokens/second/machine, same as the shared local-hosting formula), average load needs ceiling(578.70 / 8.4) = 69 machines; peak load would need ceiling(1,736.11 / 8.4) = 207 machines, a gap of 138 machines. The trigger fires whenever instantaneous demand on the Very Large tier exceeds the 69-machine fleet sized for the daily average: rather than keep 138 extra machines running 24/7 for a 4-hour window, the system routes the overflow above baseline capacity to the paid API.

### Local and API model choice

Model 10 is the primary local candidate for this scenario: it is Rishabh's highest-scoring Stage 2 model (8.44/10 mean, `llm-test/results/a7_stage2_summary.csv`), and its 5.51-second mean latency was measured on a real GPU (Colab T4, NF4, double quantization, FP16 compute) rather than CPU, so it is at least directionally representative of the production A10G reference machine's interactive behavior, though the Colab and AWS environments are not identical and no standardized rerun was done on the reference machine itself.

Model 8 is explicitly **not** proposed as a peak-hours local option despite its comparable quality (8.04/10 mean): its only measured latency, 615.87 seconds/request, was on local CPU with no MPS path, which is unusable for interactive peak traffic. This is a known gap, not a judgment on the model's quality, and a production decision would require a GPU retest of Model 8 before it could be considered here, consistent with the "Hardware and reproducibility limits" section's caution against attributing speed differences solely to model size.

The paid fallback reuses Rishabh's verified Model 10 proxy quote in `llm-test/a7_api_pricing.json` (entry 10): `Qwen/Qwen3-8B` on `nscale`, USD 0.07 input / USD 0.18 output per million tokens, checked 2026-10-22. As recorded there, this paid 8B model is smaller than the local 12B Mistral-Nemo NF4 model it backs up; no size or quality equivalence is claimed, the same disclosure standard as the Paid Hugging Face provider comparison table above.

### Fallback behavior

New requests during a peak-hours trigger route first to the already-warm local Model 10 fleet up to its provisioned baseline capacity (69 machines in the illustration above); demand beyond that capacity routes to the `Qwen/Qwen3-8B`/nscale API. If the API is unavailable or itself saturated, requests queue briefly against a latency budget rather than silently degrading quality; if the queue is not drained within that budget, the system degrades to a faster, already-capacity-rich local tier (for example the Small or Medium categories) instead of dropping the request, and that degraded response is logged as a capacity event rather than a normal-routing record. No fallback step substitutes a fabricated or cached response for a failed generation.

### Expected benefit

The benefit is avoiding 24/7 provisioning of peak-only capacity. Running the 138-machine gap as dedicated local capacity around the clock would cost 138 x USD 1.006/hour x 24 x 30 = USD 99,956.16/month at the 100,000 DAU tier, almost all of it idle outside the assumed 4 peak hours/day. Routing only the overflow above baseline capacity to the paid API during those 4 hours, using the same input/output token ratio and the shared monthly-cost formula from the Paid Hugging Face provider comparison section, costs an estimated USD 107.42/month in provider charges plus USD 36.00/month in gateway cost (one gateway machine suffices at this overflow volume), for a total of about USD 143.42/month against the same illustration. This is a planning illustration built on the peak-multiplier assumption above, not a measured production saving, but the gap between the two approaches is large enough that provisioning for average load and bursting to the paid API during peak hours is clearly preferable to provisioning for peak load locally at this tier.

### Latency, cost and quality, evaluated separately

Consistent with this document's convention of not collapsing unlike measurements into one score:

- **Latency.** Model 10 locally: 5.51 seconds mean per request, measured on Colab T4 NF4 (`a7_stage2_summary.csv`). The `Qwen/Qwen3-8B`/nscale API's latency under load has not been measured here; a production rollout would need to benchmark provider latency before relying on it for an interactive latency budget during peak hours.
- **Cost.** Baseline local fleet at the 100,000 DAU tier: USD 49,978.08/month for 69 machines. Overflow routed to the API instead of a dedicated 138-machine peak fleet: about USD 143.42/month versus USD 99,956.16/month, both figures resting on the peak-multiplier and peak-window assumptions stated above, not on measured traffic.
- **Quality.** Model 10 scored 8.44/10 mean across its 25 shared prompts; the `Qwen/Qwen3-8B` proxy's task quality on these same prompts has not been benchmarked, the same limitation already disclosed for every paid-API proxy row in the Paid Hugging Face provider comparison table. A real peak-hours rollout should not assume the API fallback matches Model 10's measured quality without separately testing it.

Final cross-scenario and cross-model routing conclusions, including whether this scenario should extend to other tiers or categories, belong to Ashley's all-model integration, consistent with the scoping already stated in "Stage 1 scope and evidence" and "Cost limitations" above.

## Stage 3 benchmarks, hardware and failed runs

Stage 3 adds Models 11–15 (Shivani): 125 new benchmark records on the same unchanged 25 prompts, scored with the same rubric as Stages 1 and 2, plus 30 local and 30 paid API cost rows. Models 1–10, their scored files and the earlier routing sections are unchanged.

| Model | Category | Mean score | Mean latency seconds | Mean output tokens per second | Token cap hits |
|---|---|---:|---:|---:|---:|
| SmolLM2-360M-Instruct | Tiny | 5.16 | 1.35 | 36.53 | 2 |
| Qwen2.5-1.5B-Instruct | Small | 7.08 | 6.10 | 13.01 | 2 |
| Qwen2.5-3B-Instruct | Medium | 7.80 | 3.87 | 23.15 | 1 |
| Qwen2.5-7B-Instruct | Large | 8.60 | 6.94 | 10.68 | 1 |
| Qwen2.5-14B-Instruct | Very Large | 8.96 | 13.90 | 5.26 | 0 |

Scores are subjective manual evaluations of the saved responses and single-run measurements, as in Stages 1 and 2. Mean latency for different models is not a controlled comparison, because the models ran on different hardware and precision (below).

| Model | Hardware | Precision and loading | Notes |
|---|---|---|---|
| 11, 12 | Apple Silicon Mac, CPU only (macOS 15.6.1 arm64, 4 CPU threads, torch 2.14.1, Python 3.12.13) | `backend="cpu"`, bfloat16 through `a7_shared.run_models`; no MPS path | Same CPU convention as Stage 1 and Stage 2 |
| 13 | Kaggle notebook, Tesla T4 (15,360 MiB; 2 CPU threads; torch 2.11.0+cu128, Python 3.13.15) | `backend="cuda"`, fp16 through `a7_shared.run_models`, eager attention | No quantization |
| 14 | Kaggle, Tesla T4 | 4-bit NF4 with double quantization, **fp32 compute dtype and fp32 non-quantized layers**, eager attention | Loaded with `llm-test/a7_stage3_nf4.py`; see failed runs |
| 15 | Kaggle, Tesla T4 | 4-bit NF4 with double quantization, **bfloat16 compute dtype and bfloat16 non-quantized layers**, eager attention | Loaded with `llm-test/a7_stage3_nf4.py` |

Latency is the `generate` call only, as in earlier stages: greedy decoding (`do_sample=False`), 256 new tokens maximum, CUDA synchronization before and after on GPU runs, no warm-up pass and no repeated runs. Model loading, tokenization and decoding are excluded. torch reported 4 CPU threads on the Mac and 2 on the Kaggle machine. Transformers, bitsandbytes and accelerate versions were not recorded in the CSV runtime field, and exact model revisions were not pinned.

### Deviation from the shared NF4 convention (Models 14 and 15)

The shared helper loads NF4 models with an fp16 compute dtype. Both Stage 3 NF4 models are Qwen2.5 models; fp16 activations can overflow in some Qwen2.5 configurations, and Model 14's first run below matches that failure pattern. The shared loader (`a7_shared.py`) was not modified. Models 14 and 15 were instead run with a loader that replaced `a7_shared.load_model` for the run only and then called the unchanged `run_models`; that loader is now committed as `llm-test/a7_stage3_nf4.py`, which is the single source of truth for these two configurations.

| Setting | Shared loader | Model 14 | Model 15 |
|---|---|---|---|
| Quantization | NF4, double quantization | same | same |
| `bnb_4bit_compute_dtype` | float16 | **float32** | **bfloat16** |
| `torch_dtype` (non-quantized layers) | float16 | **float32** | **bfloat16** |
| `device_map`, attention, `trust_remote_code` | `{"": 0}`, eager, False | same | same |
| Protocol ID hashes `nf4_compute` | `fp16` | `fp32` | `bf16` |

Reproducibility correction (no model was rerun). The saved Model 14 and 15 files originally carried the shared helper's protocol ID, which hashes `nf4_compute: fp16` and therefore described a configuration that was not used. Their `Protocol ID` is now the same hash recomputed with the real compute dtype (`protocol_id_nf4` in `a7_stage3_nf4.py`), and their `Runtime` field gained `nf4_compute`, `torch_dtype` and `loader`. Only those two columns changed in `a7_model_14_*.csv`, `a7_model_15_*.csv` and `a7_stage3_all_benchmarks.csv`; every measurement, response and score is byte-for-byte unchanged. The `Precision` column still reads `nf4`. `python llm-test/a7_stage3_nf4.py 14` (or `15`) re-runs a model with exactly these settings on a CUDA GPU, and completed 25-row files are never overwritten. Stage3Checks in `validate_a7.py` fails if an NF4 result's compute dtype, `Runtime` metadata and protocol ID disagree, if the shared fp16-compute hash is used for a non-fp16 run, or if the loader's configuration changes. The original runs were launched from ad-hoc Kaggle notebook cells that applied these same settings; those cells were not saved as files.

Model 14 had two failed attempts. Both are reported here and neither is used in any results file.

1. **fp16 compute (shared helper unchanged).** 25 records generated, 19 of 25 reached the 256-token cap, mean latency 11.49 s. The responses were corrupted: repeated `!` characters in place of text (for example `!finish!!!!! finish!!!!!!!!!!! project!!! report! !!`). This is consistent with an fp16 overflow. Discarded as an invalid run, not scored.
2. **bfloat16 compute.** 25 coherent records, mean latency 7.38 s, one cap hit. The text contained corrupted digits (for example `99 AM`, `90:30 AM`, `10:8 AM`, `p PM`, `15:00 PM`). A draft scoring gave 171 of 250. Because corrupted digits made the schedule outputs unusable, this run was replaced by attempt 3 rather than reported as a measurement.
3. **fp32 compute with fp32 non-quantized layers.** Clean, coherent records. This is the run in `a7_model_14_benchmark.csv`.

Model 15 was run with bfloat16 compute and produced clean output with no digit corruption. fp32 non-quantized layers were not tested for Model 15 because the embedding and output layers alone would need roughly 6 GB in fp32 on top of the 4-bit weights, which was not expected to fit in 15 GB.

Two further execution notes. First, Model 13 was first run on a Colab T4 (mean latency 3.91 s); that CSV was lost when the session reset and Colab then refused further GPU sessions. It was re-run on Kaggle, producing the same generated-token counts and a mean latency of 3.87 s, and only the Kaggle record is committed. Second, the quality ordering is monotonic by size for these Qwen2.5 models, but NF4 quality is not identical to full-precision quality and Model 14's and 15's different compute dtypes may affect both quality and speed.

### Observations carried into routing

Mean score by prompt type, from the saved scored files (five prompts per cell, single run):

| Model | Task Classification | Structured Extraction | Plan Summarization | Priority Ranking | Schedule Generation |
|---|---:|---:|---:|---:|---:|
| 11 (360M) | 5.4 | 5.0 | 7.0 | 5.2 | 3.2 |
| 12 (1.5B) | 8.0 | 8.8 | 8.0 | 6.0 | 4.6 |
| 13 (3B) | 9.0 | 8.6 | 8.8 | 6.0 | 6.6 |
| 14 (7B) | 9.0 | 9.0 | 8.8 | 8.4 | 7.8 |
| 15 (14B) | 9.0 | 9.0 | 8.2 | 9.2 | 9.4 |

Single-constraint tasks (classification, extraction, summarization) are handled nearly as well by the 3B model as by the 14B model. Multi-constraint tasks (priority ranking with explicit deadlines, schedule generation with durations and fixed windows) separate the models sharply. Priority Ranking exposed the same weakness noted in Stage 2: Models 11, 12, 13 and 14 each ranked laundry above an exam due tomorrow (P2), and Models 12 and 13 ranked groceries above a report due tomorrow (P1). These two observations motivate the two routing scenarios below.

## High-Complexity Queries routing scenario

Stage 3 adds two routing scenarios. This first one covers high-complexity queries. Like the Peak Usage Hours scenario above, it reuses the shared traffic tiers, throughput assumptions (Very Large 12, Large 20 and Medium 30 tokens/second at 70% utilization) and cost model, and adds only the explicitly labeled planning assumptions stated below. Numbers are illustrations at the 100,000 DAU tier, not measured production savings.

### Trigger

A request is routed as high-complexity when it is a Schedule Generation or Priority Ranking request that contains at least one of: two or more fixed time windows, an explicit deadline, or total required durations that must fit a stated window. A lightweight rule-based check on the request text (counting time expressions, durations and deadline words) is sufficient for the illustration; the classifier's accuracy has not been measured here. These are the two prompt types where the benchmark shows the largest quality gaps between model sizes.

**Planning assumption (not measured traffic):** 40% of requests are high-complexity, because two of the five benchmark prompt types are Schedule Generation or Priority Ranking and the benchmark weights the five types equally. Real traffic mix must be measured before relying on this.

### Selected models

- **Primary local model: Model 15, `Qwen/Qwen2.5-14B-Instruct` (Very Large, NF4).** It scored 9.4 on Schedule Generation and 9.2 on Priority Ranking, versus 7.8 and 8.4 for Model 14 and 6.6 and 6.0 for Model 13.
- **Local fallback: Model 14, `Qwen/Qwen2.5-7B-Instruct` (Large, NF4).** Faster and cheaper, with lower complex-task quality.
- **API fallback: `Qwen/Qwen3-14B` on `nscale`,** USD 0.07 input and 0.20 output per million tokens, read from the official Hugging Face provider listing on 2026-10-24 (entry 15 in `llm-test/a7_api_pricing.json`). Same nominal size as Model 15 but a different generation; its task quality on these prompts has not been benchmarked here.

### Fallback behavior

High-complexity requests go first to the Model 15 fleet. If the queue exceeds the latency budget, they go to the Model 14 fleet, and if that is also saturated, to the `Qwen3-14B`/nscale API. If a response fails a format check (for example a schedule whose listed durations do not sum to the requested amounts, or unparseable JSON), the request is retried once on the next tier and the event is logged. No fallback substitutes a cached or fabricated response.

### Expected benefit

The benefit is quality on the requests where small models fail. On the 25 benchmark prompts, moving Schedule Generation from Model 13 to Model 15 raised the mean score from 6.6 to 9.4, and Priority Ranking from 6.0 to 9.2. At 100,000 DAU, 40,000 complex requests per day produce 20,000,000 output tokens per day. Serving them on Model 15 needs ceiling(20,000,000 / (12 × 86,400 × 0.7)) = 28 machines, USD 20,280.96/month. Serving the same traffic on Model 14 needs 17 machines (USD 12,313.44/month), so the quality premium of Model 15 over Model 14 on these prompts (+1.6 on Schedule Generation, +0.8 on Priority Ranking) costs about USD 7,967.52/month at this tier under the shared cost model. Serving the same complex traffic through the `Qwen3-14B` API would cost 30 × (10,000,000 × 0.07 + 20,000,000 × 0.20) / 1,000,000 = USD 141.00/month in provider charges plus USD 36.00/month for one gateway, USD 177.00/month, but that price rests on an unbenchmarked proxy and an unmeasured latency.

### Latency, cost and quality, evaluated separately

- **Latency.** Model 15 measured 23.60 seconds mean on Schedule Generation and 15.63 seconds on Priority Ranking (Kaggle T4, NF4, bfloat16 compute). Model 14 measured 13.45 and 6.63 seconds (T4, NF4, fp32 compute); Model 13 measured 6.24 and 5.33 seconds (T4, fp16). The environments differ and the assumed A10G reference machine was not used, so these are directional. Model 15's measured throughput of 5.26 tokens/second on the T4 is below the shared 12 tokens/second assumption, which means the machine counts above may understate the fleet needed on T4-class hardware. API latency was not measured.
- **Cost.** Local figures above come from the shared cost model; API figures use the sourced prices and the shared gateway assumption. Neither includes queue or peak-load headroom.
- **Quality.** Scores are the single-run manual scores in the table above. The API proxy's quality is unmeasured, and the router's classification accuracy is unmeasured: a complex request misrouted to Model 13 would be expected to score closer to 6 than 9.

## Cost Optimization routing scenario

### Trigger

A request is routed as simple when it is a single-constraint Task Classification, Structured Extraction or Plan Summarization request, that is, the request does not match the high-complexity rule above. The trigger is the complement of the high-complexity rule, so each request has exactly one primary route. The same 40% complex and 60% simple traffic-mix planning assumption applies.

### Selected models

- **Primary local model: Model 13, `Qwen/Qwen2.5-3B-Instruct` (Medium, fp16).** It scored 9.0 on Task Classification, 8.6 on Structured Extraction and 8.8 on Plan Summarization, against 9.0, 9.0 and 8.2 for Model 15.
- **Escalation model: Model 15** (the high-complexity primary) for any simple request whose output fails validation.
- **API option for simple traffic: `Qwen/Qwen3-4B-Instruct-2507` on `nscale`,** USD 0.01 input and 0.03 output per million tokens, re-read from the official listing on 2026-10-24 (entry 13 in `llm-test/a7_api_pricing.json`). It is about 1.3 times larger than Model 13 and of a different generation.

### Fallback behavior

Simple requests go to the Model 13 fleet. A response is validated cheaply: JSON must parse, every task named in a classification request must receive a category, and a requested sentence count must match. A response that fails validation is re-run once on Model 15 and logged as an escalation. If the Model 13 fleet is saturated, simple requests overflow to the `Qwen3-4B-Instruct-2507` API instead of waiting. No fallback fabricates a response.

### Expected benefit

At 100,000 DAU, 60,000 simple requests per day produce 30,000,000 output tokens per day. On Model 13 (30 tokens/second assumption) this needs ceiling(30,000,000 / (30 × 86,400 × 0.7)) = 17 machines, USD 12,313.44/month. The 40% complex traffic stays on Model 15 at 28 machines, USD 20,280.96/month. The routed total is USD 32,594.40/month, against USD 49,978.08/month (69 machines) for sending all traffic to Model 15. The planning saving is USD 17,383.68/month, 34.8%, at this tier. Weighting the measured per-type means by the assumed mix gives a blended score of 0.6 × 8.8 + 0.4 × 9.3 = 9.0 for the routed system, against 8.96 for Model 15 alone, a difference well inside single-run, manual-scoring noise. An all-API alternative for simple traffic (`Qwen3-4B-Instruct-2507`) would cost USD 31.50/month in provider charges at this tier before the gateway.

### Latency, cost and quality, evaluated separately

- **Latency.** On the benchmark prompts the 3B model averaged 2.59 seconds across the three simple types (Task Classification 2.80, Structured Extraction 3.14, Plan Summarization 1.82) against 10.10 seconds for the 14B model (6.65, 14.72, 8.92). Both ran on the Kaggle T4, but with different precision settings and compute dtypes, so the ratio is directional.
- **Cost.** USD 32,594.40/month routed versus USD 49,978.08/month all-14B under the shared assumptions; escalations from Model 13 to Model 15 add Model 15 load that is not modeled here (a 10% escalation rate would add about 3,000,000 output tokens/day).
- **Quality.** Model 13 and Model 15 differ by at most 0.6 on any simple type in this single run, in either direction. The routed blended score assumes the router sends every request to the correct tier; misrouting complex requests to Model 13 is the main quality risk.

Final cross-scenario and cross-model routing conclusions, including whether these scenarios extend to other tiers or categories, belong to Ashley's all-model integration, consistent with the scoping stated earlier in this document.

## Team handoff and safe execution

The notebook resolves paths from either repository root or `llm-test` and displays all Stage 1 benchmark and cost rows. Run All imports no model inference libraries, downloads no weights and writes no authoritative CSVs. Results-only dependencies and the environment used to execute saved outputs are documented in `llm-test/a7-results-requirements.txt`. Full inference requires separately tested torch/Transformers/accelerate and bitsandbytes installations.

`a7_shared.registry` covers all 15 models. `run_models` defaults to execute=False. Future experiments require explicit execute=True, model numbers, backend, precision and a fresh stage-specific output directory. Gemma 2 gets the system instruction prepended to a user message because its template rejects system turns; Qwen3 thinking is disabled. Gemma also requires license acceptance and external HF authentication. Large models may need NF4. Never commit tokens or weights.

Completed historical records are validated and returned unchanged without loading models, regardless of new-run hardware arguments. Partial historical files are not silently resumed. New partial files require matching protocol, normalized precision, backend and runtime metadata. Precision aliases such as torch.bfloat16/bfloat16, float16/fp16 and 4-bit NF4/nf4 are recognized without rewriting CSVs. Future measured files record runtime metadata; model revision pinning remains the experimenter's responsibility. Only explicitly enabled new benchmark files use atomic per-prompt writes; scored files are never written by the helper.

`calculate_costs(numbers, model_matrix, throughput, api_models, ...)` requires sourced model/provider metadata and separate input/output prices. It returns tables and never writes files. Rishabh and Shivani add their own throughput assumptions and verified quotes for their assigned models. They must not regenerate Stage 1 measurements or scored files. Stage 1 aggregation deliberately remains scoped to Models 1–5; later stages append separately and final integration combines them.

Run `python llm-test/validate_a7.py` for Stage 1 regression checks; use `--execute-notebook` to additionally execute the notebook from both supported working directories without saving it. No model inference is needed. The existing `verify_stage1.py` is an A6 verifier and is outside this change's scope.
