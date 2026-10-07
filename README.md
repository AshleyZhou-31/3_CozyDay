# CozyDay

CozyDay is a warm, highly customizable personal life dashboard designed for
students who want structure without the pressure of traditional
productivity tools. It brings academic responsibilities and everyday life
into one supportive space — helping users identify what matters today,
organize tasks and events, track mood and daily activities, record small
moments, and receive gentle personalized encouragement.

The root page provides shared navigation to the main CozyDay areas. The
PlanItem list links each item to its primary-key detail page using the model's
`get_absolute_url()` method, keeping model, URL, view, and template routing in
one consistent end-to-end flow.

**Team 3:** Ashley Zhou · Lin Gao · Rishabh Puri · Shivani Shivani

---

## Tech Stack

- Python 3.12
- Django 5.2.17
- SQLite (default database)
- Matplotlib (server-side charts)

---

## Project Structure

- `cozyday/` — Django project package (settings, URLs, WSGI/ASGI entry points)
- `planner/` — Django app containing the core data models (`Category`,
  `PlanItem`, `DailyCheckIn`, `LifeEntry`, `WeeklyReflection`), admin
  configuration, and views
- `docs/` — project-level documentation (wireframes, branching strategy,
  weekly notes)
- `planner/docs/` — Part 4 technical documentation (data model notes, ER
  diagram, CRUD/test evidence)

---

## Setup Instructions

1. Clone the repository and enter the project directory:
   ```bash
   git clone https://github.com/AshleyZhou-31/3_CozyDay.git
   cd 3_CozyDay
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up your environment variables. Copy the example file:
   ```bash
   cp .env.example .env
   ```
   Generate a real secret key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   Paste the generated value into `.env`:
   ```
   DJANGO_SECRET_KEY=<your generated key>
   ```
   `.env` is git-ignored and must never be committed. If you skip this
   step, `manage.py` will raise an error explaining what's missing.

5. Apply migrations:
   ```bash
   python manage.py migrate
   ```

6. Create your own local superuser (do not share credentials):
   ```bash
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```bash
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000/admin/` for Django Admin.

8. Optional: seed demo PlanItems for the four view examples:
   ```bash
   python manage.py seed_rishabh_data
   ```
   Then visit `/planitems/manual/`, `/planitems/render/`,
   `/planitems/cbv-base/`, and `/planitems/cbv-generic/`.

   The canonical PlanItem list is available at `/planitems/`; select any item
to open its detail page. Also visit `/planitems/search/` to try the title search (GET and POST),
the category filter, and the grouped item-per-category summary.

---

## Static Files and CSS

Section 3 adds Django static-file support and custom CSS styling for the CozyDay interface. The shared stylesheet is located at `planner/static/planner/style.css` and is loaded through the base template so that styling is applied consistently across pages.

The PlanItem list was tested in both normal and empty states. Screenshots are available in `docs/screenshots/section3/`.

---

## Forms and User Input

Section 5 adds user input handling to the PlanItem list using a Django ModelForm and class-based view. Users can filter PlanItems by title with a GET form and create new PlanItems with a POST form protected by CSRF.

The forms were tested for GET filtering, successful POST creation, and invalid input validation. Screenshots are available in `docs/screenshots/section5/`.

---

## A5.1 Part 1: Internal Django Authentication

CozyDay now includes internal Django username/password authentication with custom login and signup pages.

### Authentication Routes

- `/login/` — custom username/password login page
- `/signup/` — custom account registration page
- `/logout/` — POST-only logout route

Authentication redirect settings are configured in `cozyday/settings/base.py`:

- `LOGIN_URL = "login"`
- `LOGIN_REDIRECT_URL = "planner:planitem-list"`
- `LOGOUT_REDIRECT_URL = "home"`

### Navigation Behavior

Anonymous users see:

- Home
- Login
- Sign Up

Authenticated users see:

- Home
- Plan Items
- Admin
- Analytics
- Reports
- Logout

Protected navigation links are hidden from anonymous users.

### Protected Pages

Authentication is required for the private CozyDay pages, including:

- `/planitems/`
- `/planitems/manual/`
- `/planitems/render/`
- `/planitems/cbv-base/`
- `/planitems/cbv-generic/`
- `/planitems/<pk>/`
- `/planitems/search/`
- `/planitems/analytics/`
- `/planitems/reports/`
- `/charts/category-summary/`
- `/charts/activity-over-time/`

### Protected APIs and Data Endpoints

The following endpoints currently require authentication:

- `/api/summary/`
- `/planitems/api/plan-items/`
- `/planitems/api/export/csv/`
- `/planitems/api/export/json/`
- `/planitems/api/external/books/`
- `/planitems/chart/category.png`
- `/vega-lite/chart1.png`
- `/vega-lite/chart2.png`

A later A5.1 stage will select exactly one database-backed API for anonymous public access.

### Manual Verification

The authentication flow was manually verified for:

- successful username/password login
- invalid login handling
- successful signup
- duplicate username handling
- logout and session termination
- anonymous private-page redirect to login
- authenticated private-page access
- anonymous protected-API redirect
- authenticated protected-API access
- anonymous and authenticated navigation states

The complete Django test suite contains 44 passing tests, including focused authentication tests.

---

## Development vs. Production Settings

Settings are split into a package at `cozyday/settings/`:

- **`base.py`** — settings shared by both environments
- **`development.py`** — used by default via `manage.py`; sets
  `DEBUG = True` and allows `localhost` / `127.0.0.1`
- **`production.py`** — used by `wsgi.py` / `asgi.py`; sets
  `DEBUG = False` and requires `DJANGO_ALLOWED_HOSTS` to be set in the
  environment (comma-separated), or the app will refuse to start

To run a command locally against production settings instead of the
default:
```bash
DJANGO_SETTINGS_MODULE=cozyday.settings.production DJANGO_ALLOWED_HOSTS=example.com python manage.py check
```

---

## Documentation

- `docs/wireframes/` — low-fidelity wireframes for CozyDay's screens
- `docs/branching-strategy/` — how the team uses branches and PRs
- `docs/notes/notes.txt` — weekly progress notes, reminders, and
  challenges (updated weekly)
- `docs/screenshots/section2/` — browser evidence for the four PlanItem views
  (Assignment 2) and the ORM search/aggregation page (Assignment 3)
- `docs/screenshots/section3/` — normal and empty template states
- `docs/screenshots/section4/` — chart image endpoint and analytics page
- `docs/screenshots/section6/` — JSON API output and response header comparison
- `planner/docs/` — Part 4 technical documentation: data model notes, ER
  diagram, and CRUD/test evidence
- `docs/screenshots/part1/` — Assignment 4 Part 1: raw API response and
  both chart pages
- `docs/vega_lite/` — committed Vega-Lite chart specifications
- `docs/screenshots/a5/lin_part1/` — A5.1 Part 1 authentication evidence, including anonymous/authenticated navigation, login/signup behavior, protected redirects, API access, and passing tests
---

## Data Visualization — Plan Items by Category

A server-side bar chart shows how many plan items belong to each category.

- **Analytics page:** `/planitems/analytics/` (chart with heading, caption,
  and alt text; also linked from the main navigation)
- **Chart image endpoint:** `/planitems/chart/category.png` (returns the PNG
  directly)

The counts come from a Django ORM aggregation
(`Category.objects.annotate(item_count=Count("plan_items"))`), so the chart
always reflects the current database. Matplotlib renders the chart into an
in-memory `BytesIO` buffer, and the view returns it as `image/png`, so no
chart files are written to disk.

Screenshots are available in `docs/screenshots/section4/`.

---

## API — Plan Items
A protected JSON endpoint exposes plan item data to authenticated CozyDay users.

```
GET /planitems/api/plan-items/
```

Returns all plan items as JSON, with only safe fields — no user IDs or
account-identifying information:

```json
{
  "results": [
    {
      "id": 7,
      "title": "Pick up dry cleaning",
      "item_type": "TASK",
      "timing": "WHENEVER",
      "is_completed": false,
      "category": "Errands"
    }
  ]
}
```

**Filtering** is supported via query parameters:

- `?category=<name>` — filter by category name (case-insensitive), e.g.
  `/planitems/api/plan-items/?category=School`
- `?completed=true` or `?completed=false` — filter by completion status,
  e.g. `/planitems/api/plan-items/?completed=true`

**Response type:** this endpoint returns `Content-Type: application/json`
via Django's `JsonResponse`, unlike the app's regular pages (e.g.
`/planitems/`), which return `Content-Type: text/html` via a rendered
template. Confirmed via browser dev tools — see
`docs/screenshots/section6/`.


---

## Internal Chart API and Vega-Lite Charts (Assignment 4, Part 1)

A dedicated internal API returns chart-ready JSON, and two pages embed
live Vega-Lite charts built from it.

**Chart-ready API:**

```
GET /api/summary/

```

As of A5.1 Part 1, this endpoint requires authentication. A later A5.1 stage will select one database-backed API for public anonymous access.

Returns two pre-aggregated lists — no raw per-record data, just what the charts need:

```json
{
  "category_counts": [
    {"name": "School", "item_count": 3}
  ],
  "activity_over_time": [
    {"date": "2026-09-24", "count": 2}
  ]
}
```

`category_counts` comes from
`Category.objects.annotate(item_count=Count("plan_items"))`.
`activity_over_time` groups `PlanItem` by `scheduled_date` and counts items
per date, excluding items with no scheduled date set.

**Chart pages:**

- `/charts/category-summary/` — Vega-Lite bar chart of plan items per
  category
- `/charts/activity-over-time/` — Vega-Lite line/point chart of plan items
  by scheduled date

Both pages load Vega, Vega-Lite, and Vega-Embed from a CDN and point their
spec's `data.url` at `/api/summary/` (using `format.property` to pull out
the relevant list). Neither spec hard-codes any values — every chart
re-renders from the live database on each page load. The full spec files
are committed at `docs/vega_lite/chart1_category_summary.json` and
`docs/vega_lite/chart2_activity_over_time.json`.

**Dedicated chart image outputs** (Matplotlib-rendered PNGs, matching the
same data as the two charts above):

- `/vega-lite/chart1.png`
- `/vega-lite/chart2.png`

Screenshots of the raw API response and both rendered charts are in
`docs/screenshots/part1/`.

---

## Exports and Reports

Section 3 (A4 Part 3) adds downloadable PlanItem exports and a reports page summarizing the data.

**Reports page:** `/planitems/reports/` — shows a total plan item count, a
completed count, a breakdown of plan items per category, and a breakdown
of completed vs. open items by item type. Visible Download CSV and
Download JSON buttons link to the two export endpoints below.

**CSV export:** `/planitems/api/export/csv/` — returns `text/csv` as a
timestamped attachment (`planitems_YYYY-MM-DD_HH-MM.csv`). All PlanItems
are included, in a consistent field order, written with Python's `csv`
module so commas, quotes, and special characters in fields like `notes`
are escaped correctly.

**JSON export:** `/planitems/api/export/json/` — returns a pretty-printed
(`indent=2`) JSON file as a timestamped attachment
(`planitems_YYYY-MM-DD_HH-MM.json`), with `generated_at`, `record_count`,
and the full `plan_items` list in the same order as the CSV. `user_id` is excluded from both exports since it isn't needed for grading and should not be exposed in downloaded data.

Both exports and the reports page were tested against the seeded
database and against an empty database (no categories, no plan items),
confirming the reports page shows its empty-state messages and both
exports still return a valid, header-only / empty-list file rather than
erroring.

Screenshots are available in `docs/screenshots/part3/`.




## A4 Part 2: External API Integration

CozyDay integrates with the Open Library Search API, a public API that does not require an API key.

### External API

Endpoint:
https://openlibrary.org/search.json

CozyDay sends the user's search term using the `q` query parameter.

Example CozyDay endpoint:

`/planitems/api/external/books/?q=study`

As of A5.1 Part 1, the CozyDay endpoint requires authentication because its response also includes database-backed CozyDay information.

The external request uses:

- `params={"q": query}`
- `timeout=5`
- `raise_for_status()`

Open Library currently documents a default rate limit of 1 request per second for non-identified requests and 3 requests per second for identified requests that include appropriate application/contact information. The API is intended for low-volume, real-time lookup rather than bulk data harvesting.

### Response Processing

CozyDay does not forward the full Open Library response. It returns up to five results and keeps only:

- title
- author
- first_publish_year

The processed external results are combined with a CozyDay database value, `cozyday_match_count`, which counts PlanItems whose titles contain the same search query. External API data is not saved to the CozyDay database.

The endpoint handles:

- missing queries
- request timeouts
- connection errors
- non-success HTTP responses
- invalid JSON
- no-results responses

### Static Files and Dependencies

Source static files are stored under `planner/static/`.

`STATIC_URL` is defined in the base settings, while production settings define:

`STATIC_ROOT = BASE_DIR / "staticfiles"`

The generated `staticfiles/` directory is ignored by Git and is created with `collectstatic` for deployment.

`base.html` loads Django static files and links to `planner/style.css` using the `{% static %}` template tag.

The project dependencies in `requirements.txt` include `requests` for the Open Library integration and `matplotlib` for chart generation.

Production settings and `collectstatic` were tested locally before deployment.
Screenshots for A4 Part 2 are available in `docs/screenshots/part2/`.



## A4 Part 4: PythonAnywhere Deployment and Online Verification

The integrated CozyDay `main` branch was deployed successfully to PythonAnywhere.

Deployed site:

https://lingao5.pythonanywhere.com/

Production deployment configuration:

- Python 3.12
- Dedicated virtual environment: `/home/lingao5/.virtualenvs/cozyday`
- Source code and working directory: `/home/lingao5/3_CozyDay`
- Production settings module: `cozyday.settings.production`
- Environment variables are loaded from a local `.env` file that is not committed to the repository.
- The committed `requirements.txt` was installed successfully on PythonAnywhere.
- `collectstatic` completed successfully, collecting 128 static files.
- `/static/` is mapped to `/home/lingao5/3_CozyDay/staticfiles`.
- The committed SQLite database was available on PythonAnywhere, and the Django production system check completed without issues.

The following deployed features were verified successfully:

- Home page with production styling
- Internal API: `/api/summary/`
- Category summary chart: `/charts/category-summary/`
- Activity-over-time chart: `/charts/activity-over-time/`
- External Open Library API integration: `/planitems/api/external/books/?q=study`
- Reports page: `/planitems/reports/`
- CSV export
- JSON export

Deployment evidence is available in `docs/screenshots/part4/`.