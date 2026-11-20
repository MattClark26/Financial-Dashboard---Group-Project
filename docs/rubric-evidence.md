# Rubric evidence register

This register maps every grading criterion to concrete evidence. Update the status and links throughout development instead of reconstructing them immediately before submission.

Status values are `Not started`, `In progress`, `Ready for review` and `Verified`.

## Group criteria (40 marks)

| Criterion | Required evidence | Owner | Status |
| --- | --- | --- | --- |
| Documentation (10) | README with setup and usage; architecture and methodology notes; data-source citations; screenshots; limitations and troubleshooting | Group | In progress |
| Attribution (10) | Named ownership in `CONTRIBUTIONS.md`; focused commits and reviewed pull requests; shared-work acknowledgements | Group | In progress |
| Reproducibility (20) | Pinned environment; one documented run path; cached fallback data; configuration example; automated tests; successful clean-machine check; live deployment | Group | Not started |

## Rohi Aluede individual criteria (40 marks)

| Criterion | Required evidence | Planned location | Status |
| --- | --- | --- | --- |
| Data-source access (10) | Source registry with provider, series identifier, URL, frequency, licence/terms, retrieval time and fallback; resilient retrieval code | Financial Stress panel documentation and data module | Not started |
| Data complexity (10) | Date alignment; causal standardisation; drawdown calculation; composite stress score; recession-event matching; false-alarm and lead-time analysis | Financial Stress analytics module, methodology and tests | Not started |
| Interactive design (10) | As-of-date behaviour; series and threshold controls; accessible charts; recession shading; tooltips; metric explanations; responsive layout | Financial Stress Streamlit view and screenshots | Not started |
| Individual Git contribution (10) | A sequence of focused commits and a reviewed pull request covering data, analytics, UI, tests and documentation | Rohi branch and pull request | In progress |

## Individual journal (20 marks)

| Required evidence | Location | Status |
| --- | --- | --- |
| Dated record of goals, decisions, work completed, problems, testing, evidence and reflection | `docs/journals/rohi-alueude.md` | In progress |

## Verification gates

A criterion should be marked `Verified` only when another group member has followed the evidence and confirmed it. Before submission, complete these checks:

- Clone the repository into a clean directory and follow only the README.
- Run the automated test suite and record the result.
- Start the dashboard without API credentials and confirm the documented fallback works.
- Start it with live data access and confirm provenance metadata is displayed.
- Select historical dates and verify that later observations cannot influence the result.
- Check all source and internal navigation links.
- Review the contribution table against the Git history and merged pull requests.
- Confirm that each journal describes real work and references verifiable evidence.
