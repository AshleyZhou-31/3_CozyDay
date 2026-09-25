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
- `planner/docs/` — Part 4 technical documentation: data model notes, ER
  diagram, and CRUD/test evidence
