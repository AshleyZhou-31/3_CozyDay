# A10 Stage 4 — Final integration and submission runbook

This package is the final handoff for the CozyDay AI System Evaluation &
Analytics Dashboard. The staff-only dashboard is available at
`/planitems/system-analytics/` and brings the three required categories into
one responsive page.

## Requirement coverage

| Category | Questions answered | Dashboard evidence |
| --- | --- | --- |
| System performance | How does latency vary? Which pipeline stage is slowest? How often do requests succeed, abstain, or fail? | mean/median/P95 cards, 14-day latency chart, stage-time chart, outcome chart |
| User behavior | How often is the planner used? Which topics are common? What query lengths, templates, and ratings occur? | 14-day volume, topic chart/table, length distribution, feedback distribution, template table |
| Cost | What is total and mean estimated cost? Which topics use the most tokens/cost? How do model/backend and generation time affect cost? | cost KPIs, cost/token charts, cost-vs-time table, backend comparison |

The dashboard uses means, median, P95, distributions, trends over time, and
group comparisons. Raw prompts, answers, retrieved text, and user IDs are not
stored. Query category and character count are derived values only. Access is
restricted to staff accounts.

Real records are shown by default. Add `?simulated=1` to include the clearly
labelled demonstration dataset; the page never silently mixes the two.

## Local or production setup

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput --settings=cozyday.settings.production
python manage.py seed_ai_analytics
python manage.py check
python manage.py test
```

Create the required grading account without storing its password in Git:

```bash
export A10_REVIEWER_PASSWORD='<password supplied in Canvas>'
python manage.py setup_a10_reviewer --username mohitg2
unset A10_REVIEWER_PASSWORD
```

The command creates or updates an active staff account, does not grant
superuser status, and never prints the password. The password required by the
assignment should be supplied only in the Canvas submission comments.

## Production QA checklist

1. Deploy the latest `main`, install requirements, migrate, collect static
   files, and reload the web app.
2. Run `seed_ai_analytics` once; rerunning is safe and replaces only simulated
   rows.
3. Sign in as `mohitg2` in a private browser window.
4. Confirm `/planitems/system-analytics/` loads and shows real-only provenance.
5. Open `?simulated=1`; confirm the simulated-data banner and all performance,
   user-behavior, feedback, template, cost, token, and backend widgets.
6. Check desktop and phone widths, then capture the final production
   screenshots with the production URL visible.
7. Confirm a normal non-staff account receives HTTP 403 and an anonymous user
   is redirected to login.

## Submission checklist

- production dashboard URL
- GitHub repository URL
- PDF (maximum 1.5 pages) with nine questions, widget mapping, statistical
  thinking, and dashboard screenshots
- final production screenshots
- grading credentials in Canvas comments: `mohitg2` and the assigned password
- passing `python manage.py check` and full Django test suite

Existing evidence is under `docs/a10_stage1/`, `docs/a10_stage2/`,
`docs/a10_refinement/`, and `docs/ai_stage3_cost_monitoring/`. Replace or
supplement it with production screenshots before final submission.
