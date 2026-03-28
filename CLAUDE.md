# SHRN.TO Market Press Intelligence

Streamlit multi-page demo app pro zpracování novinových článků pomocí AI.

## Struktura

- `app.py` — landing page
- `pages/1_Upload.py` — upload souborů
- `pages/2_Brief.py` — brief / přehled článků
- `pages/3_Export.py` — export
- `processing/pipeline.py` — jádro zpracování

## Technologie

- Streamlit
- PyMuPDF (fitz)
- python-docx
- Anthropic Claude API (model: `claude-sonnet-4-20250514`)

## Persony

Dvě persony: `investment_professional` a `decision_maker`.

## Datový model článku

Každý článek obsahuje: `headline`, `author`, `full_text`, `article_type`, `source`, `primary_category`, `secondary_tags`, `relevance_scores`, `summaries`.

## Secrets

API klíče v `.streamlit/secrets.toml`.

## Známé problémy

- PDF processing pomalý kvůli rate limitům
- DOCX segmentace podle oddělovačů
- Persona přepínání a relevance slider musí filtrovat správně
