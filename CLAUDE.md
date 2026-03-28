# SHRN.TO Market Press Intelligence

Streamlit multi-page demo app pro zpracování novinových článků pomocí AI.

## Struktura

- `App.py` — landing page
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

Dvě persony: `investment_professional` ("Investiční profesionál") a `decision_maker` ("Generická role").

## Datový model článku

Každý článek obsahuje: `headline`, `author`, `full_text`, `article_type`, `source`, `primary_category`, `secondary_tags`, `relevance_scores`, `summaries`.

## Secrets

API klíče v `.streamlit/secrets.toml`.

## Segmentace dokumentů

- **PDF**: stránka-po-stránce — každá stránka se posílá zvlášť do Claude API, články s `continuation: true` se mergují s předchozím článkem (`segment_articles_from_pdf`)
- **DOCX**: segmentace podle strukturálních oddělovačů (čáry, section headers) (`segment_articles_from_docx`)
- **TXT**: chunking celého textu a segmentace přes Claude API (`segment_articles`)

## Známé problémy

- PDF processing pomalý kvůli rate limitům (1 API call per stránka + 2s sleep)
- Persona přepínání a relevance slider musí filtrovat správně
