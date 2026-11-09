# Stage 4 Final QA Record

Date: November 9, 2026  
Branch: `a9-stage4-final-integration`

This file records the final commands and repository checks. Values are updated only
after the commands complete on the final Stage 4 branch.

## Automated checks

- `python manage.py check`: **passed**, no issues.
- Focused RAG test modules: **43/43 passed**.
- Full `python manage.py test`: **156/156 passed**.
- `python -m pip check`: **passed**, no broken requirements in the isolated QA environment.
- `git diff --check`: **passed**.

## Repository review

- New/active A9 code and documentation use repository-relative paths. A scan also found
  historical `/home/lingao5/...` paths in the older PythonAnywhere deployment notes;
  these are labeled historical configuration evidence and are not used by A9 runtime code.
- Common API-key, token and private-key patterns: **none found**.
- Tracked `.env`, `.pt`, `.bin`, `.safetensors`, `.gguf` or `.ggml` files: **none found**.
- Files over 10 MB outside Git internals: **none found**.
- Relative Markdown links in the root README and Stage 4 package: **all resolve**.
- Stage 3 final CSV: **14 rows, 14 unique case/variant pairs**, covering Q1–Q5 and
  X1–X2 for both baseline and improved variants.
- `db.sqlite3` remains a tracked 188 KB legacy demo database from earlier assignments.
  Stage 4 did not modify it. Removing it during final integration could erase shared
  demonstration data on collaborators' checkouts, so this is recorded as a deliberate
  historical exception rather than silently deleting it.

## Real-model evidence

The Stage 3 committed evaluation ran seven cases through the authenticated Django page
with the real MPNet and Qwen models. Stage 4 uses Q1, Q3 and X1 for the live rehearsal.
The final QA machine did not have the Hugging Face models cached; downloading approximately
6.5 GB solely to repeat already-committed deterministic evidence was intentionally avoided.
The authoritative real-model evidence is the 14-row final CSV and four integrated-page
screenshots, while all 156 automated integration and regression tests were rerun on the
final branch.
