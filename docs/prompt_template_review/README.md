# Prompt-template review: fixes and real comparison results

## Detector fixes

Longer planning horizons take precedence over shorter task intervals. Tests
cover `this week`, `four weeks`, `next month`, `12 weeks`, numeric/hyphenated
forms, and weekly milestones within monthly requests. The `one month` wording
in sample 2 now selects monthly instead of falling back to general.

On the original branch, literal `four weeks` already selected monthly. Actual
failures included `four-week plan`, `weekly milestones for four weeks`, and
the comparison command's `one month` wording.

## Evidence and reproduction

Lin ran the following command in the local Windows `cozyday-ai` environment on
November 12, 2026, after applying the detector and comparison-command fixes:

```powershell
python manage.py compare_prompt_templates --output docs/prompt_template_review/comparison_results.json --max-time-seconds 300
```

The terminal output contains six successful records: general/weekly,
general/monthly, and general/three_month. All warnings are null. The full
outputs are in [comparison_results.json](comparison_results.json), written by
the command on Lin's computer. This report evaluates those actual outputs;
it does not use mocked test responses or the unsuccessful CPU experiment.
The command checkpoints each completed variant, and reports errors or
abstentions rather than silently counting them as successful plans.

All three fixed public questions come from
`planner/management/commands/compare_prompt_templates.py`. No production
requests or analytics records are used in this comparison.

## Evaluation criteria

- **Timeframe correctness:** the stated horizon agrees with the request; the
  organization of tasks within that horizon is assessed separately.
- **Structure completeness:** all six required fields are present and pass the
  response schema. Empty deadline lists are allowed when no deadlines were supplied.
- **Actionability:** concrete tasks, sequencing, and next steps help a user act.
  Unsupported appointments or deadlines reduce reliability even when specific.

## Results

| Case | General prompt | Specialized prompt | Comparison |
| --- | --- | --- | --- |
| Weekly study plan | Correct `one week` horizon; all six fields; 5 tasks and 3 next steps. Identifies study topics, retrieval practice, writing, and checkpoints. | Correct `one week` horizon; all six fields; 9 tasks and 3 next steps. Adds lecture review, discussion preparation, drafting, revision, and feedback. | Specialized output is more detailed, but neither provides a complete day-by-day schedule. Both assume an exam that the prompt did not mention. The weekly variant invents a Monday class and Wednesday/Friday submission deadlines. More detail is not a clear overall improvement. |
| Monthly research proposal | Correct `one month` horizon; all six fields; 6 tasks and 3 next steps. Sequence covers topic, literature, outline, draft, feedback, and finalization; milestones extend to Day 30. | Correct `one month` horizon; all six fields; 6 tasks and 2 next steps. Explicitly includes research questions/hypotheses and methodology, with a dependency from literature review to drafting. | Specialized output improves some task specificity and dependency wording, but does not explicitly organize weekly milestones. Its draft is scheduled for Day 30, leaving no explicit revision time within the month. Both invent intermediate dates rather than clearly labeling them as suggestions. |
| Three-month dissertation chapter | Correct `three months` horizon; all six fields; 4 tasks and 3 next steps. Covers themes, literature, drafting, and revision; deadlines refer to three months but are not clearly mapped to tasks. | Correct `three months` horizon; all six fields; 5 tasks and 3 next steps. Names introduction drafting and a second section, and maps milestones to Mid-Month 1, End of Month 2, and End of Month 3. | Specialized output gives clearer month-linked milestones and more specific writing tasks. It still does not divide the task list into three explicit monthly phases, and its intermediate deadlines were not supplied by the user. |

## Conclusions

1. Both conditions returned the requested horizon in **3/3 cases** and passed
   the six-field schema in **3/3 cases**. These measures show no improvement
   from specialization in this small comparison. Schema success does not
   establish factual accuracy or full instruction compliance.
2. Specialized prompts improved some task specificity and temporal organization,
   most visibly for the three-month chapter. Improvements were mixed: the weekly
   version added unsupported commitments, and the monthly version left revision
   timing unclear.
3. All six outputs populated `deadlines`. The weekly question supplied no
   deadline; the monthly and three-month questions supplied overall horizons,
   not the specific intermediate deadlines generated. The prompts' instruction
   against inventing commitments was therefore not reliably followed. Null
   warnings and `status: success` mean the pipeline/schema checks passed, not
   that these content issues were detected.
4. Further quality work should distinguish proposed milestones from confirmed
   deadlines, avoid assuming exams or class dates, reserve revision time, and
   check temporal organization beyond the `time_period` label. These are observed
   limitations, not additional implemented fixes claimed by this report.

Three illustrative cases do not establish a general or statistically reliable
advantage of specialized prompts.

## Test verification

The repaired implementation's full Django suite passed **178 tests** in the
review environment (Python 3.12, Django 5.2.17). See
[test_results.txt](test_results.txt) for the recorded run and
[environment.txt](environment.txt) for installed packages. Django system checks
passed, and the migration dry-run reported no changes.

Negative-path tests intentionally log simulated model/API errors. These tests
use mocks where appropriate; the real generation evidence above comes from
Lin's separate local-model run. This report does not claim that Lin reran the
full Django suite merely by running the comparison command.
