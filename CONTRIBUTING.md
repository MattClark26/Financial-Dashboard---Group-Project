# Contributing to Recession Radar

The goal of this workflow is to keep individual ownership visible while making the integrated dashboard reproducible and reviewable.

## Before starting

1. Agree who owns the task and record it in `CONTRIBUTIONS.md`.
2. Create a focused branch from the latest `main`.
3. If the work changes a shared interface, add or update an entry in `docs/decision-log.md` before multiple panels depend on it.
4. Identify which rubric evidence the work will create.

Suggested branch names include `panel-3-financial-stress`, `docs/reproducibility` and `fix/as-of-date-filter`.

## Commit standard

- Keep commits focused on one coherent change.
- Use an imperative subject that explains the result, such as `feat: calculate peak-to-trough drawdowns`.
- Do not combine unrelated panel work merely to increase commit count.
- Include tests with the behaviour they protect, or explain in the pull request why a test is not appropriate.
- Do not rewrite another contributor's authorship. Credit pair work and reused material explicitly.
- Never commit credentials, private keys or local Streamlit secrets.

## Data and analytical changes

Any new or replaced series must document its provider, stable identifier, URL, frequency, units, retrieval date, transformation and fallback route.

Analytical changes must state:

- the information available at the selected as-of date;
- the treatment of missing values and mixed frequencies;
- the thresholds or fitted parameters used;
- the expected behaviour on empty or stale data;
- how the result was validated.

## Pull requests

Complete the repository pull-request template. The reviewer should be able to connect the change to a rubric criterion and reproduce the claimed behaviour.

Before requesting review:

```bash
git diff --check
python -m pytest -q
```

Add formatter, linter and type-check commands here once the group chooses those tools. A pull request should not claim a check passed unless it was actually run.

## Review standard

A reviewer should check correctness, historical integrity, failure handling, clarity, accessibility and attribution—not only whether the application starts. Changes to the shared panel result contract or scoring scale require explicit group agreement.

After merge, update the relevant contribution, rubric and journal evidence with the final commit or pull-request link.
