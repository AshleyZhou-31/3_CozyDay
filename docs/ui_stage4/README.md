# UI Stage 4 — Integration and final quality pass

Ashley Zhou completed the final UI integration pass after the Stage 3 analytics,
reports, charts, and AI-page work was merged.

## Scope

- Reworked the shared navigation into a persistent desktop sidebar and a horizontally
  scrollable mobile navigation bar.
- Rebuilt Home around the approved **person first, tasks second** hierarchy while
  keeping every call to action connected to an existing feature.
- Reworked Login and Sign Up with explicit labels, inline validation, readable help
  text, Google OAuth actions, privacy guidance, and clear secondary links.
- Added useful, branded states for cancelled and failed Google authentication.
- Brought the new RAG Planner page into the existing Stage 3 card and form system.
- Normalized typography, spacing, buttons, form controls, cards, empty-state surfaces,
  and page width in the shared stylesheet.

## Accessibility checks

- A keyboard-visible **Skip to main content** link is present on every page.
- Interactive controls have visible `:focus-visible` outlines and minimum 44 px targets.
- The current navigation destination uses `aria-current="page"`.
- Authentication and RAG forms use explicit labels and alert roles for errors.
- Heading order begins with one page-level heading on the revised Home and auth pages.
- Color pairs use darker text and button colors than the prior global stylesheet.
- Motion is effectively disabled when `prefers-reduced-motion` is enabled.

## Responsive checks

The final pass was checked at desktop and phone widths. At 900 px the sidebar becomes
a top navigation bar. At 680 px cards collapse to one column, actions become full width,
and form controls remain within the viewport without horizontal page overflow.

## Behavior preserved

No data model, authentication, authorization, API, export, chart, or AI service behavior
was changed. The revision only changes templates, styling, state presentation, and UI tests.
Anonymous users still see only public navigation. Authenticated users keep access to their
private plan items and tools, staff users keep the Admin link, and logout remains POST-only.

## Visual verification

Home and Login were rendered from the merged Stage 3 baseline and again after the
Stage 4 changes. The final desktop views were visually inspected in a real browser;
responsive behavior is enforced by the documented 900 px and 680 px breakpoints and
covered by the final manual mobile check before deployment.

## Verification commands

```text
python manage.py check
python manage.py test
git diff --check
```
