# Recession Radar browser preview

This folder contains the exact static source used by the GPT-hosted Recession
Radar preview. It is committed so collaborators can inspect and run the visual
reference without relying on a separate hosted copy.

From the repository root, run:

```sh
python -m http.server 4173 --directory preview-site
```

Then open `http://localhost:4173`.

The preview is a presentation mirror for reviewing the design. The graded,
data-backed application starts from `app.py` and runs with Streamlit. Changes to
the dashboard logic belong in the Streamlit application first, then should be
reflected here when the visual reference is updated.
