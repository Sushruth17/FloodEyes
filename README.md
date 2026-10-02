# Flood Eyes

**Flood Hub forecasts the flood. Flood Eyes measures it.**

Live street-level flood depth from crowdsourced photos, built on Gemini and Google Cloud for the
Google Cloud AI Builder Cup 2026 (Sustainability & Social Impact). See [PLAN.md](PLAN.md) for the
full design.

> Status: Day 1, feasibility test in progress. The product sections of this README will be filled in
> as components land.

## Feasibility test (run this first)

```bash
# 1. Environment
cd backend && python3 -m venv .venv && .venv/bin/pip install uv
.venv/bin/uv pip install --python .venv/bin/python -e ".[eval]" pytest pytest-asyncio ruff
cp ../.env.example ../.env          # add GEMINI_API_KEY (AI Studio) for local eval
.venv/bin/pytest -q                  # unit tests
cd ..

# 2. Collect openly licensed photos (licence and author are recorded in eval/data/manifest.csv)
backend/.venv/bin/python eval/fetch_commons.py --search "waterlogging road India" --limit 20

# 3. Label independently (see eval/LABELING_GUIDE.md)
backend/.venv/bin/python eval/label_server.py --labeller a               # http://localhost:8765
backend/.venv/bin/python eval/label_server.py --labeller b --port 8766

# 4. Agreement + adjudication
backend/.venv/bin/python eval/adjudicate.py            # then resolve eval/labels/conflicts.csv
backend/.venv/bin/python eval/adjudicate.py --resolve

# 5. Evaluate (model × prompt matrix). Results: eval/results/LATEST.md + confusion matrix PNGs
backend/.venv/bin/python eval/run_depth_eval.py \
    --models gemini-3.8-flash,gemini-3.5-flash-lite --prompts v1,v2 --split dev
```

**Go/no-go:** car-passability accuracy ≥ 80 % and false-safe rate ≤ 10 %.

## Repo layout
- `backend/app/agents/`: Gemini agents and versioned prompts (`prompts/depth_v*.md`)
- `backend/app/models/`: structured-output schemas
- `backend/app/fusion/passability.py`: deterministic safety rules (the model estimates depth; code decides passability)
- `backend/cities/`: per-city config (reference heights, passability thresholds)
- `eval/`: dataset tools, labelling app, metrics, evaluation runner

## Photo licences
Every evaluation photo's source, licence and author are listed in `eval/data/manifest.csv`.
