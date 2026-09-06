# CozyDay — Part 4 Notes: Data Modeling & Admin Kickoff

**Team 3** · Ashley Zhou · Lin Gao · Rishabh Puri · Shivani Shivani
**App:** `planner` (Django app within the CozyDay project)

---

## 1. Project Overview

CozyDay is a warm, customizable life dashboard that helps students organize
academic and personal life in one place without the pressure of a rigid
productivity tool. Part 4 establishes the foundational data model: five
Django models that support planning, mood tracking, quick notes, and weekly
reflection, all scoped to an individual user.

This document covers the model design, relationships, deletion behavior,
constraints, ordering, migration steps, CRUD/test evidence, setup
instructions, and team responsibilities for Part 4.

**Repository:** https://github.com/AshleyZhou-31/cozyday (private)
**Environment:** Python 3.12.10 · Django 5.2.17 · project `cozyday` · app `planner`

---

## 2. Model Purposes

| Model | Purpose |
|---|---|
| **Category** | A user-created label (e.g. School, Personal, Wellness) used to organize `PlanItem`s without duplicating category names per user. |
| **PlanItem** | A task or event a user wants to organize — powers the Today / This Week / Later / Whenever planning views. |
| **DailyCheckIn** | A user's optional mood and energy check-in for a single calendar day — supports daily awareness without streak pressure. |
| **LifeEntry** | A note, idea, or meaningful everyday moment — powers Quick Capture and the "My Life" history. |
| **WeeklyReflection** | A user's editable written reflection for a given week, stored separately from auto-summarized activity data. |

Each model's docstring in `models.py` states what real-world entity it
represents and why it exists in the system, per the assignment requirement.

**Alignment with the CozyDay feature set:**

| CozyDay feature (from project proposal) | Backed by |
|---|---|
| Flexible Planning / Today's Focus | `PlanItem` |
| Mood Tracking | `DailyCheckIn` |
| Life Log and Quick Capture | `LifeEntry` |
| Weekly Reflection and Summary | `WeeklyReflection` |
| Customizable Dashboard labels | `Category` |

The five models cover every proposed feature **except** Personalized Daily
Cheer and the Capacity Gauge / Low-Capacity Mode. Those are intentionally
**not** given their own tables — they are computed/derived features that
will read from `PlanItem` and `DailyCheckIn` at request time rather than
storing precomputed results. This keeps the schema minimal for Part 4 while
still supporting those features once the logic is built in a later part.

---

## 3. Relationships

- **User → Category** (one-to-many): every `Category` belongs to exactly one
  user. `on_delete=CASCADE` — a category has no meaning without its owner.
- **User → PlanItem** (one-to-many): every `PlanItem` belongs to exactly one
  user. `on_delete=CASCADE`.
- **User → DailyCheckIn** (one-to-many): `on_delete=CASCADE`.
- **User → LifeEntry** (one-to-many): `on_delete=CASCADE`.
- **User → WeeklyReflection** (one-to-many): `on_delete=CASCADE`.
- **Category → PlanItem** (one-to-many, **optional**): a `PlanItem` may
  optionally belong to one `Category` (`null=True, blank=True`).
  `on_delete=SET_NULL` — deleting a category should not delete the tasks
  attached to it.

See the ER diagram in `docs/er_diagram.png` (or `.pdf`) for the full visual
model.

---

## 4. Deletion Decisions (Rationale)

| Relationship | on_delete | Why |
|---|---|---|
| User → all 5 models | `CASCADE` | All planner data is personally owned and has no meaning independent of the user. If a user account is deleted, their categories, plan items, check-ins, entries, and reflections should be removed with it — there is no legitimate reason to retain orphaned personal data. |
| Category → PlanItem | `SET_NULL` | A category is a light organizational label, not a required attribute of a task. Deleting a category (e.g. a student removes a "Work Study" label they no longer use) should not destroy the tasks that were filed under it — those tasks still matter and simply become uncategorized. This preserves the user's task history and avoids unexpected data loss from a low-stakes cleanup action. |

This distinction — cascade for ownership relationships, `SET_NULL` for
optional organizational relationships — is the core deletion-behavior logic
for the schema.

---

## 5. Unique Constraints

Three multi-field uniqueness constraints prevent duplicate/conflicting data
per user:

1. **`unique_category_per_user`** — `(user, name)` on `Category`. Prevents a
   single user from creating two categories with the same name.
2. **`unique_daily_check_in_per_user`** — `(user, date)` on `DailyCheckIn`.
   Prevents more than one check-in per user per calendar day.
3. **`unique_weekly_reflection_per_user`** — `(user, week_start)` on
   `WeeklyReflection`. Prevents more than one reflection per user per week.

All three are scoped per-user (not globally unique), since the same name,
date, or week is legitimately reused across different users.

---

## 6. Default Ordering

| Model | Ordering | Rationale |
|---|---|---|
| Category | `name` | Alphabetical — predictable for selection dropdowns/filters. |
| PlanItem | `is_completed`, `scheduled_date`, `scheduled_time`, `title` | Incomplete items surface first; within that, soonest-scheduled items appear first, matching how a planning view should read. |
| DailyCheckIn | `-date` | Most recent check-in first, matching a daily-log reading pattern. |
| LifeEntry | `-entry_date`, `-created_at` | Most recent entries first, for a Quick Capture / history feed. |
| WeeklyReflection | `-week_start` | Most recent week first. |

---

## 7. Migration Commands

```bash
python manage.py makemigrations
python manage.py migrate
```

Confirm no unexpected changes and a clean migration state:

```bash
python manage.py makemigrations --check
python manage.py migrate
python manage.py check
python manage.py showmigrations planner
```

`0001_initial` should show as applied (`[X]`) under the `planner` app.

---

## 8. CRUD Evidence and Test Results

*(Sourced from Lin's Admin/CRUD screenshots and Rishabh's data-seeding and
uniqueness-test results — to be inserted once their branches are merged.)*

### 8.1 Admin Configuration & CRUD (Lin — branch `lin-admin`)
- [ ] Screenshot: Admin homepage showing all 5 models registered
- [ ] Screenshot: model list view (list_display / list_filter / search_fields)
- [ ] Screenshot: Create/Edit form for a model
- [ ] Screenshot (before/after): `SET_NULL` — deleting a temporary Category
  and confirming the linked `PlanItem` survives with an empty category
- [ ] Screenshot (before/after): `CASCADE` — deleting a temporary
  non-superuser account and confirming their related records disappear

### 8.2 Test Data & Uniqueness Constraints (Rishabh — branch `rishabh-data-testing`)
- [ ] Confirmed seed data: ~5 Categories, 8–10 PlanItems (covering
  Task/Event, all 4 timing choices, completed/incomplete, with/without
  category), 5+ DailyCheckIns, 5+ LifeEntries, 3+ WeeklyReflections
- [ ] `unique_category_per_user` — duplicate attempt rejected: **[result]**
- [ ] `unique_daily_check_in_per_user` — duplicate attempt rejected: **[result]**
- [ ] `unique_weekly_reflection_per_user` — duplicate attempt rejected: **[result]**

*(Update this section with actual outcomes/screenshots once Lin and
Rishabh's PRs are merged into `main`.)*

---

## 9. Setup Instructions

```bash
# 1. Clone the repo and enter the project directory
git clone <repo-url>
cd <project-folder>

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Create a superuser (or use the existing one)
python manage.py createsuperuser

# 6. Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/admin/` to access Django Admin.

**Superuser credentials:** username `mohitg2`, password `uiuc12345`, per the
assignment's main instructions and the account Ashley already created.

> ⚠️ **Flag for the instructor:** the assignment sheet lists two different
> superuser credentials — `mohitg2` / `uiuc12345` in the main Part 4
> instructions, and `tester` / `uiuc12345` in the Step-by-Step Checklist.
> This project uses `mohitg2` to match the main instructions. Confirm with
> the grader if `tester` was actually expected.

---

## 10. Design Notes

- **Naming:** `<startproject_folder_name>` represents the overall CozyDay
  project; the `planner` app name was chosen because it represents the core
  feature domain (planning, check-ins, reflections) housed in Part 4's data
  model, distinct from other feature apps that may be added later.
- **Data integrity note:** `DailyCheckIn.mood` and `energy` are `blank=True`,
  meaning a check-in can technically be saved with no mood/energy recorded.
  This is intentional — CozyDay is designed to avoid pressuring users into
  mandatory daily input — but it means downstream features (e.g. weekly mood
  summaries) should treat blank fields as "not reported" rather than a
  default/neutral value.
- **Recommended next step (Part 5+):** A lightweight aggregation model (e.g.
  `WorkloadSnapshot` or similar) could summarize `PlanItem` completion and
  `DailyCheckIn` mood/energy trends over time, feeding the "weekly stats" and
  "Personalized Daily Cheer" features without recomputing raw data on every
  page load. Flagged here for the team to evaluate in the next phase rather
  than implemented now, since it is out of scope for Part 4.

---

## 11. Team Responsibilities (Part 4)

| Member | Responsibility |
|---|---|
| **Ashley** | Project set-up and integration: environment/Django setup, model design, relationships, deletion rules, ordering, unique constraints, initial migration, Admin account, Git/GitHub setup, PR review and merging, final integration checks, final ZIP packaging. |
| **Lin** | Django Admin configuration, CRUD demonstration, and deletion-behavior tests (`SET_NULL` and `CASCADE`) with screenshot evidence. Branch: `lin-admin`. |
| **Rishabh** | Realistic test data seeding across all 5 models and uniqueness-constraint testing, doubling as data prep for upcoming Personalized Daily Cheer / weekly stats work. Branch: `rishabh-data-testing`. |
| **Shivani** | ER diagram creation and Part 4 documentation (this file) — consolidating model purposes, relationships, deletion rationale, constraints, ordering, migration steps, CRUD/test evidence, and setup instructions. Branch: `shivani-documentation`. |

---

## 12. Final Checklist (from assignment)

- [ ] `python manage.py makemigrations --check` — no unexpected changes
- [ ] `python manage.py migrate`
- [ ] `python manage.py check` — no issues
- [ ] `python manage.py showmigrations planner` — `0001_initial` is `[X]`
- [ ] All 5 models visible and functional in Django Admin (CRUD confirmed)
- [ ] Uniqueness and deletion-behavior evidence attached
- [ ] ER diagram matches actual models
- [ ] This file (`PART4_NOTES.md`) is complete
- [ ] Final ZIP includes source code, migrations, `requirements.txt`,
      documentation, ER diagram, and final `db.sqlite3`
- [ ] Final ZIP excludes `.venv`, `.idea`, caches, and secret files
- [ ] `git status` is clean and `main` is pushed to GitHub
