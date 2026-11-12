# A10 Stage 2: Prompt Templates and Structured Plans

The RAG Planner detects a requested horizon before retrieval and selects one
of four prompt variants: `weekly`, `monthly`, `three_month`, or the `general`
fallback. Three specialized templates tell the model how to organize the
plan; the general template is used when the request does not name a clear
horizon. All variants require the same JSON fields: goal, time period,
priorities, tasks or phases, deadlines, and recommended next steps.

The request text is used for detection, retrieval, and generation, but is not
stored in analytics. The analytics record stores only the selected template
identifier. The generated JSON is validated before display; invalid or
incomplete structured output produces a safe retry message instead of exposing
an unvalidated response. Relevance abstentions continue to use the existing
RAG relevance gate.

## Comparing prompt variants

With the local models installed, run:

```bash
python manage.py compare_prompt_templates
```

The command runs three fixed representative planning questions through both
the general prompt and the detected specialized prompt, then prints the
validated plans. It does not store the sample questions or create analytics
events. Compare whether specialized outputs use the intended horizon and
whether all six fields remain complete and actionable.

## Adding a template

1. Add a stable identifier to `TEMPLATE_TYPES` in `planner/plan_templates.py`.
2. Add a detection rule in `_DETECTORS` if the template should be selected from
   ordinary user wording.
3. Add the prompt text to `PROMPT_TEMPLATES`; retain the shared JSON contract
   and do not ask the model to invent dates or personal facts.
4. Add the identifier to `AIPerformanceEvent.template_type` model choices and
   create a Django migration.
5. Add detection, fallback, and structured-output tests, and include a
   representative query in the comparison command.
