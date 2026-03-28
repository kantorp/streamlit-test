from __future__ import annotations

from collections import defaultdict
from datetime import date

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Export — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CATEGORY_ORDER = ["ECON", "POL_CZ", "POL_INT", "REG", "UNKNOWN"]

CATEGORY_LABELS = {
    "ECON": "Ekonomika",
    "POL_CZ": "Domácí politika",
    "POL_INT": "Zahraniční politika",
    "REG": "Regulace",
    "UNKNOWN": "Ostatní",
}

CATEGORY_LABELS_EN = {
    "ECON": "Economy",
    "POL_CZ": "Domestic Politics",
    "POL_INT": "International Politics",
    "REG": "Regulation",
    "UNKNOWN": "Other",
}

CATEGORY_COLORS_HEX = {
    "ECON": "#1E88E5",
    "POL_CZ": "#43A047",
    "POL_INT": "#FB8C00",
    "REG": "#E53935",
    "UNKNOWN": "#9E9E9E",
}

PERSONA_LABELS = {
    "investment_professional": "📊 Investiční profesionál",
    "decision_maker": "🏛️ Generická role",
}

# ---------------------------------------------------------------------------
# Data check
# ---------------------------------------------------------------------------
articles: list[dict] = st.session_state.get("articles", [])

if not articles:
    st.title("SHRN.TO")
    st.caption("Market Press Intelligence")
    st.markdown("---")
    st.warning("Nejprve nahrajte a zpracujte dokumenty.")
    st.page_link("pages/1_Upload.py", label="📤 Přejít na nahrávání", icon="📤")
    st.stop()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("SHRN.TO")
st.caption("Market Press Intelligence")
st.markdown("---")
st.header("📥 Export briefu")

st.page_link("pages/2_Brief.py", label="← Zpět na brief", icon="📋")
st.markdown("")

# ---------------------------------------------------------------------------
# Export settings
# ---------------------------------------------------------------------------
col_persona, col_lang, col_threshold = st.columns(3)

with col_persona:
    persona = st.radio(
        "Perspektiva",
        options=list(PERSONA_LABELS.keys()),
        format_func=lambda k: PERSONA_LABELS[k],
        horizontal=True,
        key="export_persona",
    )

with col_lang:
    lang = st.radio(
        "Jazyk",
        options=["cs", "en"],
        format_func=lambda x: "🇨🇿 Čeština" if x == "cs" else "🇬🇧 English",
        horizontal=True,
        key="export_lang",
    )

with col_threshold:
    threshold = st.slider(
        "Minimální relevance",
        min_value=1.0,
        max_value=5.0,
        value=3.0,
        step=0.5,
        key="export_threshold",
    )

# ---------------------------------------------------------------------------
# Filter & sort
# ---------------------------------------------------------------------------
filtered: list[dict] = []
for a in articles:
    score = (a.get("relevance_scores") or {}).get(persona, 0)
    if score >= threshold:
        filtered.append(a)

filtered.sort(
    key=lambda a: (a.get("relevance_scores") or {}).get(persona, 0),
    reverse=True,
)

all_sources = sorted({a.get("source", "?") for a in filtered})
today_str = date.today().strftime("%d. %m. %Y")
persona_label = PERSONA_LABELS[persona]

st.info(f"**{len(filtered)}** článků bude v exportu (z celkem {len(articles)})")
st.markdown("---")

# ---------------------------------------------------------------------------
# Group by category
# ---------------------------------------------------------------------------
grouped: dict[str, list[dict]] = defaultdict(list)
for a in filtered:
    cat = a.get("primary_category", "UNKNOWN")
    grouped[cat].append(a)

suffix = "_cs" if lang == "cs" else "_en"
cat_labels = CATEGORY_LABELS if lang == "cs" else CATEGORY_LABELS_EN


# ---------------------------------------------------------------------------
# Build TXT content
# ---------------------------------------------------------------------------
def _build_txt() -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"SHRN.TO | {'Ranní brief' if lang == 'cs' else 'Morning Brief'} | {today_str}")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Zdroje' if lang == 'cs' else 'Sources'}: {', '.join(all_sources)}")
    lines.append(f"{'Profil' if lang == 'cs' else 'Profile'}: {persona_label}")
    lines.append(f"{'Článků' if lang == 'cs' else 'Articles'}: {len(filtered)}")
    lines.append("")

    for cat in CATEGORY_ORDER:
        cat_articles = grouped.get(cat, [])
        if not cat_articles:
            continue
        label = cat_labels.get(cat, cat)
        lines.append("-" * 60)
        lines.append(f"  {label.upper()}")
        lines.append("-" * 60)
        lines.append("")

        for art in cat_articles:
            summaries = art.get("summaries") or {}
            headline = summaries.get(f"headline{suffix}", art.get("headline", ""))
            extended = summaries.get(f"extended{suffix}", "")
            source = art.get("source", "?")
            score = (art.get("relevance_scores") or {}).get(persona, 0)
            tags = art.get("secondary_tags") or []

            lines.append(f"  * {headline}")
            lines.append(f"    [{source}] relevance {score:.1f} | {', '.join(tags)}")
            lines.append("")
            if extended:
                for para_line in extended.split("\n"):
                    lines.append(f"    {para_line}")
                lines.append("")
            lines.append("")

    lines.append("=" * 60)
    footer_label = "článků z" if lang == "cs" else "articles from"
    source_label = "zdrojů" if lang == "cs" else "sources"
    lines.append(f"  {len(filtered)} {footer_label} {len(all_sources)} {source_label}")
    lines.append(f"  SHRN.TO — Market Press Intelligence")
    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build HTML content
# ---------------------------------------------------------------------------
def _build_html() -> str:
    cat_sections = ""
    for cat in CATEGORY_ORDER:
        cat_articles = grouped.get(cat, [])
        if not cat_articles:
            continue
        label = cat_labels.get(cat, cat)
        color = CATEGORY_COLORS_HEX.get(cat, "#9E9E9E")

        cards = ""
        for art in cat_articles:
            summaries = art.get("summaries") or {}
            headline = summaries.get(f"headline{suffix}", art.get("headline", ""))
            extended = summaries.get(f"extended{suffix}", "")
            source = art.get("source", "?")
            score = (art.get("relevance_scores") or {}).get(persona, 0)
            tags = art.get("secondary_tags") or []
            author = art.get("author") or ""
            art_type = art.get("article_type", "")

            tag_badges = "".join(
                f'<span style="background:#555;color:#ddd;padding:1px 6px;'
                f'border-radius:3px;font-size:0.75em;margin-right:4px;">{t}</span>'
                for t in tags
            )

            meta_parts = [p for p in [author, art_type, source] if p]
            meta_line = " | ".join(meta_parts)

            extended_html = extended.replace("\n", "<br>") if extended else ""

            cards += f"""
            <div style="background:#1e1e1e;border:1px solid #333;border-radius:8px;
                        padding:16px;margin-bottom:12px;">
                <div style="margin-bottom:6px;">
                    <span style="background:{color};color:#fff;padding:2px 8px;
                                 border-radius:4px;font-size:0.8em;font-weight:600;">
                        {cat}
                    </span>
                    {tag_badges}
                    <span style="color:#FFD54F;font-size:0.85em;margin-left:8px;">
                        &#11088; {score:.1f}
                    </span>
                </div>
                <h3 style="margin:8px 0 4px 0;color:#eee;">{headline}</h3>
                <div style="color:#999;font-size:0.85em;margin-bottom:8px;">{meta_line}</div>
                <div style="color:#ccc;line-height:1.6;">{extended_html}</div>
            </div>"""

        cat_sections += f"""
        <div style="margin-bottom:24px;">
            <h2 style="color:{color};border-bottom:2px solid {color};
                       padding-bottom:4px;margin-bottom:12px;">
                {label}
            </h2>
            {cards}
        </div>"""

    sources_str = ", ".join(all_sources)
    footer_label = "článků z" if lang == "cs" else "articles from"
    source_label = "zdrojů" if lang == "cs" else "sources"
    brief_label = "Ranní brief" if lang == "cs" else "Morning Brief"

    return f"""<!DOCTYPE html>
<html lang="{'cs' if lang == 'cs' else 'en'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SHRN.TO — {brief_label} {today_str}</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #121212;
    color: #e0e0e0;
    margin: 0;
    padding: 0;
  }}
  .header {{
    background: linear-gradient(135deg, #1a237e, #0d47a1);
    padding: 24px 32px;
    color: #fff;
  }}
  .header h1 {{ margin: 0 0 4px 0; font-size: 1.8em; }}
  .header p {{ margin: 0; opacity: 0.85; font-size: 0.95em; }}
  .meta {{
    background: #1e1e1e;
    padding: 12px 32px;
    border-bottom: 1px solid #333;
    font-size: 0.9em;
    color: #aaa;
  }}
  .content {{ max-width: 900px; margin: 24px auto; padding: 0 24px; }}
  .footer {{
    text-align: center;
    padding: 24px;
    color: #666;
    font-size: 0.85em;
    border-top: 1px solid #333;
    margin-top: 32px;
  }}
</style>
</head>
<body>
  <div class="header">
    <h1>SHRN.TO</h1>
    <p>{brief_label} | {today_str}</p>
  </div>
  <div class="meta">
    {'Zdroje' if lang == 'cs' else 'Sources'}: {sources_str} &nbsp;|&nbsp;
    {'Profil' if lang == 'cs' else 'Profile'}: {persona_label} &nbsp;|&nbsp;
    {'Článků' if lang == 'cs' else 'Articles'}: {len(filtered)}
  </div>
  <div class="content">
    {cat_sections}
  </div>
  <div class="footer">
    {len(filtered)} {footer_label} {len(all_sources)} {source_label}<br>
    SHRN.TO &mdash; Market Press Intelligence
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------
st.subheader("Náhled briefu")

if not filtered:
    st.warning("Žádné články nesplňují zvolená kritéria.")
    st.stop()

# Render preview in-page
brief_label = "Ranní brief" if lang == "cs" else "Morning Brief"
st.markdown(f"### SHRN.TO | {brief_label} | {today_str}")
st.markdown(f"**{'Zdroje' if lang == 'cs' else 'Sources'}:** {', '.join(all_sources)}")
st.markdown(f"**{'Profil' if lang == 'cs' else 'Profile'}:** {persona_label}")
st.markdown("---")

for cat in CATEGORY_ORDER:
    cat_articles = grouped.get(cat, [])
    if not cat_articles:
        continue
    label = cat_labels.get(cat, cat)
    color = CATEGORY_COLORS_HEX.get(cat, "#9E9E9E")

    st.markdown(
        f'<h2 style="color:{color};border-bottom:2px solid {color};'
        f'padding-bottom:4px;">{label}</h2>',
        unsafe_allow_html=True,
    )

    for art in cat_articles:
        summaries = art.get("summaries") or {}
        headline = summaries.get(f"headline{suffix}", art.get("headline", ""))
        extended = summaries.get(f"extended{suffix}", "")
        source = art.get("source", "?")
        score = (art.get("relevance_scores") or {}).get(persona, 0)
        tags = art.get("secondary_tags") or []

        tag_html = "".join(
            f'<span style="background:#424242;color:#ddd;padding:1px 6px;'
            f'border-radius:3px;font-size:0.7em;margin-right:4px;">{t}</span>'
            for t in tags
        )
        badge = (
            f'<span style="background:{color};color:#fff;padding:2px 8px;'
            f'border-radius:4px;font-size:0.8em;font-weight:600;">{cat}</span>'
        )

        st.markdown(
            f'{badge} {tag_html} '
            f'<span style="color:#FFD54F;font-size:0.85em;">⭐ {score:.1f}</span> '
            f'<span style="color:#999;font-size:0.8em;">| {source}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{headline}**")
        if extended:
            st.markdown(extended)
        st.markdown("")

footer_label = "článků z" if lang == "cs" else "articles from"
source_label = "zdrojů" if lang == "cs" else "sources"
st.markdown("---")
st.caption(f"{len(filtered)} {footer_label} {len(all_sources)} {source_label} | SHRN.TO — Market Press Intelligence")

# ---------------------------------------------------------------------------
# Download buttons
# ---------------------------------------------------------------------------
st.markdown("---")
dl_col1, dl_col2 = st.columns(2)

with dl_col1:
    html_content = _build_html()
    st.download_button(
        label="📥 Stáhnout jako HTML",
        data=html_content.encode("utf-8"),
        file_name=f"shrn_to_brief_{date.today().isoformat()}.html",
        mime="text/html",
    )

with dl_col2:
    txt_content = _build_txt()
    st.download_button(
        label="📥 Stáhnout jako TXT",
        data=txt_content.encode("utf-8"),
        file_name=f"shrn_to_brief_{date.today().isoformat()}.txt",
        mime="text/plain",
    )
