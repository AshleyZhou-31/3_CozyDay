# UI Stage 1 — Shared Foundation Documentation

## Scope

The shared UI foundation assigned to Stage 1 was largely implemented during Ashley's Stage 4 integration and is already present on `main`. This contribution documents the existing foundation and adds visual evidence; it does not replace shared templates, navigation, styles, responsive behavior, or accessibility work.

The shared shell is in `planner/templates/base.html`; shared visual rules and reusable classes are in `planner/static/planner/style.css`. Feature-page owners should extend their page-specific styles without changing these global rules unless the team agrees on a shared change.

## Wireframe comparison

| Area | Original wireframe direction | Current implementation and intentional difference |
| --- | --- | --- |
| Home and hierarchy | PDF page 4 places Mood, Energy, and Capacity above tasks, Upcoming, and Quick Capture, with a companion cat. | Home uses a person-first hero, a supportive note, feature cards, and quick links. The welcoming tone is carried forward, but this is not the original interactive dashboard: its check-ins, companion, and Quick Capture are not represented by the current hero and feature cards. This Stage 1 documentation contribution records the difference without adding those features. |
| Plan organization and adding items | The design materials show grouped planning concepts, including Today / This Week / Whenever, and an add-item modal flow. | The current product keeps its existing Plan Items routes and forms. It does not introduce a new modal or replace the current data workflow as part of a visual refinement. |
| Navigation | The original persistent sidebar contains Home, My Plans, My Life, Reflection, and Settings. | The integrated site uses a persistent desktop sidebar and a top navigation bar at narrower widths. Navigation visibility also changes with authentication and staff status. |
| Login | No Login wireframe is included in the original PDF. | Login and Sign Up use the shared shell, explicit labels, inline validation, help text, Google sign-in actions, and privacy guidance. These details make the existing authentication flow clearer without changing its behavior. |
| Visual language | Calm, approachable styling with clear grouping and prominent actions. | The current UI uses navy headings, green primary actions, warm cream / sage / peach surfaces, rounded cards, and a consistent type hierarchy. |

The wireframes are design references rather than a specification to replace the existing routes or data behavior. Where the website differs, the implementation preserves the established feature workflow and applies the wireframes' hierarchy, grouping, and action emphasis within that workflow.

## Shared design guide

### Colors and surfaces

Use the CSS custom properties defined in `planner/static/planner/style.css`:

| Token | Value | Typical use |
| --- | --- | --- |
| `--cozy-navy` | `#17365d` | Headings and brand emphasis |
| `--cozy-ink` | `#263238` | Body text |
| `--cozy-muted` | `#586b61` | Supporting text |
| `--cozy-green` / `--cozy-green-dark` | `#3f6b45` / `#315638` | Primary action and stronger hover state |
| `--cozy-sage` | `#e8f0e4` | Soft supporting surface |
| `--cozy-cream` / `--cozy-paper` | `#fffaf3` / `#fffefa` | Warm page and content surfaces |
| `--cozy-peach` | `#f5ece1` | Secondary surface and navigation hover |
| `--cozy-line` | `#dfe6dc` | Borders and dividers |
| `--cozy-focus` | `#245d8f` | Keyboard focus outline |
| `--cozy-radius` | `16px` | Shared large radius |

### Reusable classes and components

| Class or feature | Intended use |
| --- | --- |
| `.eyebrow` | Short context label above a heading |
| `.feature-card` | Home feature with title, description, and action |
| `.cozy-button` | Primary action |
| `.cozy-button--secondary` | Secondary outlined action |
| `.button-row` | Related actions that can wrap |
| `.form-field` | Label and associated form control |
| `.field-help` / `.field-errors` | Field instructions and validation details |
| `.form-alert` | Form-level error or status message |
| `.empty-state` | Empty list or result with an appropriate next step |
| `.site-nav`, `.nav-more`, `.nav-logout` | Shared navigation, additional tools, and POST logout in `base.html` |

Keep new page-specific variants in the owning feature stylesheet. Use semantic headings, labels, buttons, links, and form controls so the visual patterns remain understandable to assistive technology.

### Layout and responsive behavior

- `base.html` provides the page shell, skip link, navigation, `main` region, and footer. Page templates fill `{% block content %}` and may use `{% block extra_head %}` for page-specific head additions.
- The desktop shell has a 236 px navigation column. Main content is capped at 1120 px and uses responsive padding.
- At 900 px, the sidebar becomes top navigation. At 680 px, cards and actions collapse for narrow screens.
- Grid and flex children should be allowed to shrink; long text should wrap; page layouts should not create horizontal overflow.
- Interactive controls have a minimum 44 px target.

### Accessibility and navigation conventions

- Every page has a keyboard-visible “Skip to main content” link.
- Links, buttons, form fields, summaries, and focusable page regions show a visible focus outline.
- The current navigation destination uses `aria-current="page"` where configured.
- Form controls have explicit labels; field errors and form-level alerts remain readable and associated with the relevant input or submission.
- Reduced-motion preferences are respected.
- Anonymous users see Home, Log in, and Sign up. Authenticated users see Home, Plan Items, Analytics, Reports, RAG Planner, More tools, and POST-based Log out. Staff users also see Admin.
- Preserve existing authentication, authorization, CSRF, and user-data isolation behavior.

## Visual evidence

The before images are original wireframe design references, not screenshots of an earlier working website. The after images show the local interface on the documentation branch created from the updated `main` checkout. Home and Login show the anonymous navigation; Plan Items is the representative authenticated page.

| Page | Before / design reference | After desktop | After mobile |
| --- | --- | --- | --- |
| Home | [Home wireframe](screenshots/before/home-wireframe.png) | [Desktop Home](screenshots/after/website_home.png) | [Mobile Home](screenshots/after/phone_home.png) |
| Login | No Login design in the original PDF | [Desktop Login](screenshots/after/website_login.png) | [Mobile Login](screenshots/after/phone_login_.png) |
| Plan Items (authenticated) | [My Plans wireframe](screenshots/before/plan-items-wireframe.png) | [Desktop Plan Items](screenshots/after/Website_planitem.png) | [Mobile Plan Items](screenshots/after/phone_planitems_.png) |

The capture procedure uses Chrome Responsive mode with a desktop viewport of 1440 x 900 CSS pixels and a mobile viewport of 390 x 844 CSS pixels, followed by Capture full size screenshot. Full-page image height can exceed the viewport height, and output pixel dimensions can differ with device pixel ratio. The viewport settings should be confirmed against the settings used for the saved captures; image dimensions alone do not establish CSS viewport width.

The source PDF contains no Login design or separate mobile wireframes. Login therefore has after-only evidence. The before images extract only the website artwork from the PDF, excluding surrounding headings, design notes, and page numbers while preserving interface text and navigation. See [source details](screenshots/before/SOURCE.md). The [Add Something reference](screenshots/before/add-something-wireframe.png), PDF page 6, supports the modal-flow comparison.

## Verification

Commands were run locally in the `cozyday-web` environment. Results below are transcribed from the terminal output:

| Check | Result |
| --- | --- |
| `python manage.py check` | Passed: no issues (0 silenced). |
| `python manage.py test planner.test_ui_stage4` | Passed: 8 tests in 0.753 seconds, OK. |
| `python manage.py test` | Passed: 135 tests in 18.269 seconds, OK. |

The full suite output includes a mocked `RuntimeError: model crashed`; the final suite result is OK. This exception output is not a failed test result.

During local setup, the Login page initially reported `no such table: django_site`. Existing database migrations were applied with `python manage.py migrate`, after which the Login page rendered. No new migration or runtime UI code was added for this setup issue. Local `db.sqlite3` changes are excluded from this documentation contribution.

Before committing, run `git diff --cached --check` and confirm that only `docs/ui_stage1/` files are staged. This contribution is documentation and visual evidence only. Stage 1 is complete after the PR is reviewed and merged.
