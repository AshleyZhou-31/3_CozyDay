# UI Stage 3: Analytics, Reports, Charts and AI Planner pages

Branch: `ui-stage3-analytics-shivani`
Scope: Analytics, Reports, the two Vega-Lite chart pages, the local AI Planner and the API Planner.
No shared template, global CSS, view, URL, model, API or auth code was changed.

## What changed
- New stylesheet `planner/static/planner/insights.css`, scoped under `.insights` and loaded only by these six pages.
- Six page templates updated; new partial `_ai_result.html` shared by both AI pages.
- **Analytics:** title, intro text, chart card, and links to Reports and the interactive charts.
- **Reports:** summary tiles, a download card, and tables with captions, `scope` attributes and Completed/Open badges.
- **Chart pages:** the chart resizes to its container, and the page has loading, empty and error states plus a text list of the chart data. The Vega-Lite spec still reads `/api/summary/` through `data.url`; no data is inlined.
- **AI pages:** privacy information, the request form, errors and generated results are shown as separate blocks. The submit button shows a busy state, an error keeps the user's text, and results are labelled by source (local model or Gemini).

## Unchanged by design
The public `/api/summary/`, protected endpoints, `login_required`, CSRF, URL names and the Vega-Lite data source. The strings the existing tests rely on are kept ("No categories yet.", "No plan items yet.", "looks incomplete").

## Accessibility
Semantic headings, landmarks, table captions and `scope`; every interactive element has a visible `:focus-visible` outline; text and button colours were chosen for WCAG AA contrast (4.5:1).

## Testing
Tested locally with two accounts: `test_data` (7 plan items across 4 categories, some completed, with scheduled dates) and `test_empty` (no data). Screenshots are in `before/` (from `main`) and `after/` (this branch), at desktop width 1440 and mobile width 390.

Automated:
- `python manage.py check`: no issues
- `python manage.py test`: 105 tests, all passing

Manual:

| Case | Desktop 1440 | Mobile 390 |
|---|---|---|
| Analytics, user with data | Chart shows inside the card | Chart fits the card |
| Analytics, user without data | Empty chart, page text still clear | Same |
| Reports with data | Totals, download buttons and both tables correct | Tables fit the card |
| Reports without data | "No categories yet." and "No plan items yet." shown | Same |
| Chart pages with data | Chart loads from `/api/summary/` | Chart resizes to the card |
| Chart pages, `/api/summary/` blocked | "Chart unavailable" message shown | Same |
| AI Planner: validation error and result | Error and result shown in separate blocks | Same |
| API Planner: validation error and API error | Error box shown; the request text is kept | Same |
| Keyboard Tab through each page | Visible outline on every link, button, checkbox and field | n/a |
| Logged out: protected pages | Redirect to login | n/a |

Content width at 390: no horizontal overflow inside the content card. The page itself can still scroll sideways because of the global navigation (shared layout, out of scope).

## Deviations from the wireframes and known limits
1. Analytics has no metric tiles. That page only shows the per-user chart image, and the totals live on Reports; adding tiles would have meant changing the view.
2. The chart pages read the public API, which serves the shared demo account, so a signed-in user's chart can differ from their Analytics page. Each chart page says so.
3. The stylesheet `<link>` sits inside the content block because `base.html` has no head block. It can move once the shared-template stage lands.
4. On narrow screens the whole page can still scroll sideways because of the global navigation in `base.html` and `style.css`. That belongs to the shared-layout stage and was not changed here.
5. This work was built against `main` before the Stage 1 and Stage 2 UI PRs. It will be rebased onto them if they merge first, and the six pages re-checked.
6. The Gemini API key is not configured on my machine, so the API Planner was tested to its error state only.
