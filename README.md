# Intelligent Finance Chatbot for Expense Tracking and Financial Insights Using RAG

**Current status: Phase 1 - manual transaction tracker (no AI yet).**

## Setup (one time)
```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# Mac / Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Run the app
```bash
streamlit run app.py
```
Your browser opens at http://localhost:8501.

## Run the tests
```bash
python -m unittest discover -s tests -t . -v
```

## Optional: demo data (clearly labelled "[SAMPLE]")
```bash
python -m scripts.load_sample_data            # add
python -m scripts.load_sample_data --remove   # remove ONLY the sample rows
```

## Folder guide
| Path | Purpose |
|---|---|
| `app.py` | Entry point + Dashboard page |
| `pages/` | Other pages (Streamlit lists them in the sidebar by filename) |
| `src/config.py` | Categories, currency, limits, database path |
| `src/database.py` | All SQLite code |
| `src/validation.py` | Checks user input before saving |
| `src/calculations.py` | All exact finance maths (plain pandas) |
| `src/charts.py` | Plotly chart builders |
| `src/ui.py` | Small shared Streamlit helpers |
| `tests/` | Automated tests |
| `scripts/load_sample_data.py` | Optional demo data |
| `data/finance.db` | Created automatically on first run (git-ignored) |
