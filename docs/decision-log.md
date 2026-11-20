# Project decision log

Record decisions that affect more than one file or grading criterion. Each entry should explain the reason, alternatives and consequences so the final submission documents the analytical process rather than only the outcome.

## D001 — Treat the as-of date as a hard information boundary

- **Date:** 2026-11-20
- **Status:** Proposed for group confirmation
- **Context:** The dashboard's time machine is intended to show what the indicators would have said at a historical date. Full-sample normalisation or later revised observations would leak future information into that view.
- **Decision:** Data retrieval, transformation, model fitting and scoring must operate on observations permitted by the selected as-of date. Tests will deliberately add future outliers and confirm that historical results do not change.
- **Consequences:** Expanding or trailing-window statistics are required. Series without vintage history must be labelled as revised-data analysis. This is more work, but makes the backtest defensible.

## D002 — Separate analytical output from Streamlit rendering

- **Date:** 2026-11-20
- **Status:** Proposed for group confirmation
- **Context:** Calculations embedded directly in widgets are difficult to test and reuse in the composite thermometer or Irish Lens.
- **Decision:** Each panel should expose testable data/analysis functions and a small rendering layer. Its standard analytical result should include a numeric score, traffic-light status, verdict, latest observation date and provenance metadata.
- **Consequences:** The exact shared interface still needs group agreement. Panel calculations can be tested without starting Streamlit, and shared components can consume consistent results.

## Decision template

### DXXX — Short title

- **Date:** YYYY-MM-DD
- **Status:** Proposed, accepted, superseded or rejected
- **Context:** What problem required a decision?
- **Decision:** What was agreed?
- **Alternatives:** What credible options were considered?
- **Consequences:** What becomes easier, harder or constrained?
