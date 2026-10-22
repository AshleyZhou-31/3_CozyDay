# CozyDay Multi-Model AI System ? Architecture and Cost Analysis

## Stage 1 ? Benchmark Foundation (Lin)

### Model Benchmarking

The system evaluates 15 Hugging Face models across five parameter-size categories, using 25 identical CozyDay prompts.

The five prompt categories are Task Classification, Priority Ranking, Schedule Generation, Plan Summarization, and Structured Extraction.

Each model output is evaluated using four equally weighted criteria: instruction adherence, accuracy, clarity, and structure.

The overall evaluation score is rounded to the nearest integer on a 1?10 scale.

### Stage 1 Experimental Results

| Model | Avg Quality | Avg Latency (s) | Avg Tokens/sec |
|---|---:|---:|---:|
| SmolLM2-135M | 2.76 | 5.19 | 24.49 |
| Qwen2.5-0.5B | 6.80 | 5.56 | 12.37 |
| Qwen3-1.7B | 8.00 | 17.34 | 4.34 |
| Phi-3.5-mini | 9.40 | 6.05 | 24.21 |
| Qwen3-8B | 9.64 | 6.66 | 11.76 |

Models 1?3 were benchmarked locally on CPU. Models 4?5 were tested using a Google Colab Tesla T4 GPU. Model 4 used FP16; Model 5 used 4-bit NF4 quantization.

Therefore, observed speed differences cannot be attributed solely to model size.

### Traffic Assumptions

- Average generated tokens per request: 500
- Requests per daily active user per day: 1
- Month length: 30 days
- Traffic categories: 1K, 10K, 100K, 1M, 10M, 100M daily active users

Daily token load = daily active users ? requests per user ? average generated tokens.

### Local Hosting Assumptions

Reference cloud configuration: AWS g5.xlarge, NVIDIA A10G 24 GB GPU.

- Assumed hourly cost: USD 1.006
- Assumed utilization: 70%
- Assumed model throughput: 60, 45, 30, 20, and 12 output tokens/sec for Models 1?5
- All cloud throughput figures are planning assumptions, not measured GPU benchmarks.

Machine count = ceiling(daily token load / (tokens/sec ? 86,400 ? utilization)).

Monthly machine cost = machine count ? hourly cost ? 24 ? 30.

Larger models may require quantization to fit the reference GPU configuration.

### Hugging Face API Cost Assumptions

The API comparison uses illustrative paid inference rates, not verified provider-specific quotes.

Assumed USD per million output tokens for Models 1?5:

- Model 1: $0.10
- Model 2: $0.20
- Model 3: $0.40
- Model 4: $0.75
- Model 5: $1.20

Assumed API gateway hourly cost: $0.05 per machine.

Assumed gateway capacity: 100 requests/second.

Monthly API cost = daily output tokens / 1,000,000 ? assumed price ? 30.

Total monthly API infrastructure cost = monthly API cost + monthly gateway cost.

### Cost Data and Limitations

Stage 1 produces 30 local hosting rows and 30 API cost rows.

Both approaches are compared in USD per month.

Cost estimates exclude input-token charges, storage, network transfer, high-availability redundancy, operational labor, and cloud discounts.

Source references:

- https://huggingface.co/docs/inference-providers/en/pricing
- https://aws.amazon.com/ec2/instance-types/g5/
- https://aws.amazon.com/ec2/pricing/on-demand/

Prices and service availability require verification before production use.

## Stage 2 ? Rishabh

To be completed by Stage 2.

## Stage 3 ? Shivani

To be completed by Stage 3.

## Stage 4 ? Ashley

Final comparison, routing analysis, verification, and submission.
