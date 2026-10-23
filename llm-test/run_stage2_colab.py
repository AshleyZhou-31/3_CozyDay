"""Stage 2 (Rishabh) — real inference for Models 9 and 10 on Colab GPU.

Upload this file plus a7_shared.py and results/research_matrix.csv to Colab
(see upload instructions given alongside this file), then in a Colab cell:

    !pip install -q "transformers>=4.46,<6" "accelerate>=1.0,<2" "bitsandbytes>=0.43,<1"
    !python run_stage2_colab.py 9
    !python run_stage2_colab.py 10

Run 9 (Qwen3-4B, FP16) and 10 (Mistral-Nemo-12B, 4-bit NF4) as SEPARATE
processes/cells, one after another -- each writes
results/a7_model_<N>_benchmark.csv atomically per prompt, so if the Colab
runtime disconnects mid-run, re-running the same command resumes safely
(same protocol/backend/precision = same protocol_id).

Neither model is gated (both Apache-2.0, per research_matrix.csv), so no HF
login should be required.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path.cwd().resolve()
MODULE_DIR = next((d for d in (HERE, HERE / "llm-test") if (d / "a7_shared.py").is_file()), None)
if MODULE_DIR is None:
    raise FileNotFoundError("a7_shared.py not found -- upload it alongside this script")
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from a7_shared import registry, validate_prompts, run_models  # noqa: E402

RESULTS_DIR = MODULE_DIR / "results"
model_matrix = pd.read_csv(RESULTS_DIR / "research_matrix.csv")
models = registry(model_matrix)

# Identical, character-for-character, to multi_model_system.ipynb's prompt cell
# and to run_stage2_local.py -- hash-verified against the notebook before use.
evaluation_prompts = [
    ("C1", "Task Classification", "Classify these tasks as Work, Study, Personal, or Health: finish project report, review lecture notes, buy groceries, and go for a run. Return one category per task."),
    ("C2", "Task Classification", "Categorize my tasks: email my supervisor, prepare for an exam, clean my room, and attend a dental appointment."),
    ("C3", "Task Classification", "Classify these activities: submit homework, schedule a team meeting, call my family, and attend a yoga class."),
    ("C4", "Task Classification", "Organize these tasks by category: write a research summary, cook dinner, review class slides, and visit the gym."),
    ("C5", "Task Classification", "Classify these tasks as Work, Study, Personal, or Health: update a client spreadsheet, study Python, pay rent, and attend a medical checkup."),
    ("P1", "Priority Ranking", "I have a report due tomorrow, groceries to buy, and a room to clean. Rank these tasks by priority and explain briefly."),
    ("P2", "Priority Ranking", "I have an exam tomorrow, a meeting next week, and laundry to finish. What should I prioritize today?"),
    ("P3", "Priority Ranking", "My presentation is due tonight, my emails can wait until Friday, and I need to exercise. Rank these tasks."),
    ("P4", "Priority Ranking", "I must submit an assignment by 5 PM, call a friend sometime this week, and prepare dinner tonight. Rank these tasks by urgency."),
    ("P5", "Priority Ranking", "I need to finish a group project due tomorrow, organize my desk, and prepare for a quiz next Monday. Give me a priority order."),
    ("S1", "Schedule Generation", "Create a schedule from 9 AM to 5 PM for studying 3 hours, exercising 1 hour, and grocery shopping 1 hour. Include breaks."),
    ("S2", "Schedule Generation", "Plan my day between 8 AM and 6 PM. I have class from 10 AM to noon, need 2 hours for homework, and want 1 hour for lunch."),
    ("S3", "Schedule Generation", "I am free from 1 PM to 9 PM. Schedule 3 hours of project work, 1 hour of exercise, and 1 hour of cooking."),
    ("S4", "Schedule Generation", "Build a realistic schedule from 9 AM to 7 PM with a meeting from 11 AM to noon, 3 hours of studying, and 2 hours of errands."),
    ("S5", "Schedule Generation", "Organize my afternoon from noon to 6 PM. I need 2 hours for research, 1 hour for groceries, and 1 hour for cleaning."),
    ("M1", "Plan Summarization", "Summarize my day: 9 AM lecture, 11 AM library study, 2 PM grocery shopping, and 6 PM dinner with friends."),
    ("M2", "Plan Summarization", "Give me a concise summary of tomorrow: morning workout, afternoon team meeting, evening homework."),
    ("M3", "Plan Summarization", "Summarize this schedule and highlight key commitments: 8 AM breakfast, 10 AM exam, 1 PM lunch, 3 PM office hours."),
    ("M4", "Plan Summarization", "Summarize my tasks in two sentences: finish readings, send emails, clean the apartment, and prepare meals."),
    ("M5", "Plan Summarization", "Provide a short daily overview: 9 AM project work, noon lunch, 2 PM class, 5 PM gym, and 7 PM dinner."),
    ("E1", "Structured Extraction", "Extract tasks and times as JSON from: I need to attend class at 9 AM, buy groceries at 4 PM, and study at 7 PM."),
    ("E2", "Structured Extraction", "Convert this into JSON with task and deadline fields: Finish the report by Friday, email the professor by Wednesday, and submit homework tomorrow."),
    ("E3", "Structured Extraction", "Extract tasks, durations, and categories into JSON: study Python for 2 hours, exercise for 45 minutes, and clean the kitchen for 30 minutes."),
    ("E4", "Structured Extraction", "Create a JSON task list from: Meeting at 10 AM, lunch at noon, project work at 2 PM, and dinner at 6 PM."),
    ("E5", "Structured Extraction", "Extract structured task data as JSON: submit the assignment by 11:59 PM, call my parents at 7 PM, and exercise for 30 minutes."),
]
prompts_df = pd.DataFrame(evaluation_prompts, columns=["Prompt ID", "Prompt Type", "Prompt"])
validate_prompts(prompts_df)

NUMBER_CONFIG = {9: dict(backend="cuda", precision="fp16"), 10: dict(backend="cuda", precision="nf4")}

if __name__ == "__main__":
    if len(sys.argv) != 2 or int(sys.argv[1]) not in NUMBER_CONFIG:
        raise SystemExit("Usage: python run_stage2_colab.py <9|10>")
    number = int(sys.argv[1])
    config = NUMBER_CONFIG[number]
    print(f"Running Model {number} ({models[number][0]}) on {config}")
    result = run_models([number], model_matrix, prompts_df, RESULTS_DIR, execute=True, **config)
    frame = result[number]
    print(f"\nModel {number}: {len(frame)} rows written.")
    print(frame[["Prompt ID", "Tokens/sec", "Latency", "Generated Tokens", "Reached Token Limit"]])
