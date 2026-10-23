"""Stage 2 (Rishabh) — real inference for Models 6, 7, 8 on local CPU.

Run this from the repo root or llm-test/, inside the real Python environment
that has torch/transformers/accelerate installed (same one used for the prior
assignment's local model runs). This performs REAL model downloads and REAL
generation — it will take a while, especially for google/gemma-2-2b-it.

Usage:
    python llm-test/run_stage2_local.py

Writes (atomically, per prompt, so it is safe to re-run if interrupted):
    llm-test/results/a7_model_6_benchmark.csv
    llm-test/results/a7_model_7_benchmark.csv
    llm-test/results/a7_model_8_benchmark.csv

Gemma 2 is a gated model: if this fails with a 403/permission error on
google/gemma-2-2b-it, run `huggingface-cli login` first and make sure the
Gemma license has been accepted on huggingface.co (same requirement as the
previous assignment).
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path.cwd().resolve()
MODULE_DIR = next((d for d in (HERE, HERE / "llm-test") if (d / "a7_shared.py").is_file()), None)
if MODULE_DIR is None:
    raise FileNotFoundError("Run from the repo root or llm-test directory")
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from a7_shared import registry, validate_prompts, run_models  # noqa: E402

RESULTS_DIR = MODULE_DIR / "results"
model_matrix = pd.read_csv(RESULTS_DIR / "research_matrix.csv")
models = registry(model_matrix)

# Identical, character-for-character, to the 25 prompts defined in
# multi_model_system.ipynb (cell under "## Prompts"). Do not edit this list
# independently of that notebook cell — protocol_id() hashes the exact text.
evaluation_prompts = [
    # Task Classification
    ("C1", "Task Classification", "Classify these tasks as Work, Study, Personal, or Health: finish project report, review lecture notes, buy groceries, and go for a run. Return one category per task."),
    ("C2", "Task Classification", "Categorize my tasks: email my supervisor, prepare for an exam, clean my room, and attend a dental appointment."),
    ("C3", "Task Classification", "Classify these activities: submit homework, schedule a team meeting, call my family, and attend a yoga class."),
    ("C4", "Task Classification", "Organize these tasks by category: write a research summary, cook dinner, review class slides, and visit the gym."),
    ("C5", "Task Classification", "Classify these tasks as Work, Study, Personal, or Health: update a client spreadsheet, study Python, pay rent, and attend a medical checkup."),
    # Priority Ranking
    ("P1", "Priority Ranking", "I have a report due tomorrow, groceries to buy, and a room to clean. Rank these tasks by priority and explain briefly."),
    ("P2", "Priority Ranking", "I have an exam tomorrow, a meeting next week, and laundry to finish. What should I prioritize today?"),
    ("P3", "Priority Ranking", "My presentation is due tonight, my emails can wait until Friday, and I need to exercise. Rank these tasks."),
    ("P4", "Priority Ranking", "I must submit an assignment by 5 PM, call a friend sometime this week, and prepare dinner tonight. Rank these tasks by urgency."),
    ("P5", "Priority Ranking", "I need to finish a group project due tomorrow, organize my desk, and prepare for a quiz next Monday. Give me a priority order."),
    # Schedule Generation
    ("S1", "Schedule Generation", "Create a schedule from 9 AM to 5 PM for studying 3 hours, exercising 1 hour, and grocery shopping 1 hour. Include breaks."),
    ("S2", "Schedule Generation", "Plan my day between 8 AM and 6 PM. I have class from 10 AM to noon, need 2 hours for homework, and want 1 hour for lunch."),
    ("S3", "Schedule Generation", "I am free from 1 PM to 9 PM. Schedule 3 hours of project work, 1 hour of exercise, and 1 hour of cooking."),
    ("S4", "Schedule Generation", "Build a realistic schedule from 9 AM to 7 PM with a meeting from 11 AM to noon, 3 hours of studying, and 2 hours of errands."),
    ("S5", "Schedule Generation", "Organize my afternoon from noon to 6 PM. I need 2 hours for research, 1 hour for groceries, and 1 hour for cleaning."),
    # Plan Summarization
    ("M1", "Plan Summarization", "Summarize my day: 9 AM lecture, 11 AM library study, 2 PM grocery shopping, and 6 PM dinner with friends."),
    ("M2", "Plan Summarization", "Give me a concise summary of tomorrow: morning workout, afternoon team meeting, evening homework."),
    ("M3", "Plan Summarization", "Summarize this schedule and highlight key commitments: 8 AM breakfast, 10 AM exam, 1 PM lunch, 3 PM office hours."),
    ("M4", "Plan Summarization", "Summarize my tasks in two sentences: finish readings, send emails, clean the apartment, and prepare meals."),
    ("M5", "Plan Summarization", "Provide a short daily overview: 9 AM project work, noon lunch, 2 PM class, 5 PM gym, and 7 PM dinner."),
    # Structured Extraction
    ("E1", "Structured Extraction", "Extract tasks and times as JSON from: I need to attend class at 9 AM, buy groceries at 4 PM, and study at 7 PM."),
    ("E2", "Structured Extraction", "Convert this into JSON with task and deadline fields: Finish the report by Friday, email the professor by Wednesday, and submit homework tomorrow."),
    ("E3", "Structured Extraction", "Extract tasks, durations, and categories into JSON: study Python for 2 hours, exercise for 45 minutes, and clean the kitchen for 30 minutes."),
    ("E4", "Structured Extraction", "Create a JSON task list from: Meeting at 10 AM, lunch at noon, project work at 2 PM, and dinner at 6 PM."),
    ("E5", "Structured Extraction", "Extract structured task data as JSON: submit the assignment by 11:59 PM, call my parents at 7 PM, and exercise for 30 minutes."),
]
prompts_df = pd.DataFrame(evaluation_prompts, columns=["Prompt ID", "Prompt Type", "Prompt"])
validate_prompts(prompts_df)

NUMBERS = [6, 7, 8]
print("Models to run:", {n: models[n] for n in NUMBERS})
print("Backend=cpu, precision=bfloat16 (matches Stage 1's historical CPU convention).")
print("This will take a while on CPU, especially google/gemma-2-2b-it. Progress is saved per prompt.")

result = run_models(NUMBERS, model_matrix, prompts_df, RESULTS_DIR,
                     execute=True, backend="cpu", precision="bfloat16")

for number, frame in result.items():
    print(f"\nModel {number} ({models[number][0]}): {len(frame)} rows written.")
    print(frame[["Prompt ID", "Tokens/sec", "Latency", "Generated Tokens", "Reached Token Limit"]])

print("\nDONE. Next: score these in a7_model_6/7/8_scored.csv (send the raw CSVs back for scoring).")
