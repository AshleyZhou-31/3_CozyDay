# CozyDay A7 RAG revision for Ashley review

Copy the a7_part2 directory contents into the same directory of your local repository.

- Part2_RAG.ipynb: corrected experiment, 14 sequentially executed code cells, saved actual fresh-process outputs.
- part2_rag_results.csv: original 25 records, unchanged; historical only.
- archive/part2_rag_results_original_14db91d.csv: identical archival copy.
- part2_matched_baseline.csv: authoritative five-run baseline for Shivani (Part 3) and Ashley (Part 4); responses and historical proxy scores unchanged.
- part2_rag_results_revised.csv: 20 corrected RAG runs, full prompts, retrieval rank, document prompt order, actual contexts, generation settings and new criterion scores.
- part2_quality_evaluation.csv: 25 evaluations (5 authoritative baseline + 20 corrected RAG), per-criterion components and explanations. Support is N/A for no-RAG. All new overall scores are 1/10; historical CSV scores are 2/10 from a different heuristic.

The highest-ranked document is now placed immediately before the unchanged question. Expected answer spans survive in 20/20 runs, but subjects in the evidence are still truncated. Four Top-K configurations collapse to the same effective context per question. Correct generated RAG answers remain 0/20. These limitations are explicitly discussed.

Set SLM_CHECKPOINT_PATH outside the notebook before launching your notebook application. Use the original frozen checkpoint. SHA256: 408c27aa60346f00a41b1cef451e434c277493fc8329061ddaec060043e78a1f.
Use question + one trailing space, seed 42, temperature 1.0 and 30 new characters for the authoritative no-RAG baseline. Before fine-tuning compare all five responses with part2_matched_baseline.csv.

## Part 4 final comparison

`Part4_Comparison.ipynb` is Ashley's executable final comparison of the same five questions under the baseline, Top-1 RAG, and fine-tuned conditions. Top-1 was selected because every tested Top-K setting tied at a mean quality score of 1.0/10 with 0/5 correct responses, while Top-1 uses the least context space. The notebook reads the committed Part 2 and Part 3 results, validates their shared questions and generation settings, and exports:

- `part4_three_condition_comparison.csv`
- `part4_condition_evaluation.csv`
- `part4_topk_selection.csv`

The complete comparison table and the five required final-analysis answers also appear in the final Markdown cell of `Part3_FineTune.ipynb`, as required by the assignment. The observed accuracy was 0/5 for the baseline, 0/5 for Top-1 RAG, and 5/5 exact first-line answers after fine-tuning; the notebook discusses the accompanying memorization, forgetting, context-length, and unsupported-output limitations.

Verified in two fresh Python processes, launched from repository root and a7_part2; both performed actual CSV writes in isolated temporary copies. Python 3.12.14, PyTorch 2.14.1+cpu, pandas 2.2.3, CPU. This is fresh-process execution, not a Jupyter-kernel test. Original CSVs, checkpoint and Part 1 remained unchanged. Retrieval-source equivalence to the unavailable Week 6 classroom notebook is not independently verified.

No commit, push, merge, retraining or checkpoint modification was performed. Run locally before staging; review only the intended files and never stage model weights.
