# UI accessibility and state audit

This audit covers the server-rendered verification UI in `proof/api.py`. It is
an evidence report, not a claim of full WCAG conformance.

## Covered in code

- Native `button`, `a`, `input`, `select`, and `label` elements are used for
  the main interaction path.
- Verification fields have programmatic `label for="..."` associations.
- Language, theme, and repository controls have accessible names.
- Keyboard focus has a visible `:focus-visible` indicator.
- Example descriptions use a polite status region.
- Errors use an assertive alert region.
- Verification results use a polite live region.
- Loading disables the Verify button while the request is in flight.
- Network and API errors are surfaced with specific text rather than silently
  leaving the user at a blank result.
- Empty, successful, failed-claim, and insufficient-evidence paths are
  represented distinctly in the UI.

## Automated evidence

`tests/test_ui_contract.py` pins the user-perceivable contract without using a
live network or implementation-private state:

- every verification field has a matching label;
- dynamic error/example/result regions have announcement semantics;
- iconographic controls have accessible names.

The test currently passes with 3 tests. The full repository suite was also
validated from a fresh clone at 161 passing tests before this audit's latest
test was added.

## Remaining manual/browser checks

These are intentionally not marked complete without a browser or assistive
technology run:

- keyboard-only traversal through the full form and example buttons;
- visible focus at desktop and narrow widths;
- contrast review in both dark and light themes;
- screen-reader wording and announcement timing;
- touch target measurement on mobile;
- loading and error behavior under a deliberately slow or failed request;
- browser-level responsive screenshots at 1440px and 375px widths.

The absence of a browser E2E dependency is a current test-surface limitation,
not evidence that these checks pass.
