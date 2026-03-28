from __future__ import annotations

from datetime import date

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Brief — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CATEGORY_COLORS: dict[str, tuple[str, str]] = {
    # category -> (background, label)
    "ECON": ("#1E88E5", "ECON"),
    "POL_CZ": ("#43A047", "POL_CZ"),
    "POL_INT": ("#FB8C00", "POL_INT"),
    "REG": ("#E53935", "REG"),
}

PERSONA_LABELS = {
    "investment_professional": "📊 Investiční profesionál",
    "decision_maker": "🏛️ Rozhodovatel",
}

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "excluded_articles" not in st.session_state:
    st.session_state.excluded_articles = set()

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
# Derived metadata
# ---------------------------------------------------------------------------
all_sources = sorted({a.get("source", "?") for a in articles})
all_categories = sorted({a.get("primary_category", "?") for a in articles})

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("SHRN.TO")
st.caption("Market Press Intelligence")

st.markdown(
    f"**{len(articles)} článků** z **{len(all_sources)} zdrojů** | {date.today().strftime('%d. %m. %Y')}"
)
st.markdown("---")

# ---------------------------------------------------------------------------
# Control panel
# ---------------------------------------------------------------------------
ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([2, 2, 2, 1.5, 1.5])

with ctrl_col1:
    persona = st.radio(
        "Perspektiva",
        options=list(PERSONA_LABELS.keys()),
        format_func=lambda k: PERSONA_LABELS[k],
        horizontal=True,
        key="persona",
    )

with ctrl_col2:
    selected_categories = st.multiselect(
        "Kategorie",
        options=all_categories,
        default=all_categories,
        key="filter_categories",
    )
    selected_sources = st.multiselect(
        "Zdroje",
        options=all_sources,
        default=all_sources,
        key="filter_sources",
    )

with ctrl_col3:
    threshold = st.slider(
        "Minimální relevance",
        min_value=1.0,
        max_value=5.0,
        value=3.0,
        step=0.5,
        key="relevance_threshold",
    )
    count_placeholder = st.empty()

with ctrl_col4:
    lang = st.radio(
        "Jazyk",
        options=["cs", "en"],
        format_func=lambda x: "🇨🇿 Čeština" if x == "cs" else "🇬🇧 English",
        horizontal=True,
        key="lang",
    )

with ctrl_col5:
    sort_by = st.selectbox(
        "Řazení",
        options=["relevance", "category", "source"],
        format_func=lambda x: {
            "relevance": "Podle relevance",
            "category": "Podle kategorie",
            "source": "Podle zdroje",
        }[x],
        key="sort_by",
    )

# ---------------------------------------------------------------------------
# Filtering — use active persona for relevance score
# ---------------------------------------------------------------------------
active_persona: str = persona  # "investment_professional" or "decision_maker"

filtered: list[dict] = []
for a in articles:
    score = (a.get("relevance_scores") or {}).get(active_persona, 0)
    if a.get("primary_category") not in selected_categories:
        continue
    if a.get("source") not in selected_sources:
        continue
    if score < threshold:
        continue
    filtered.append(a)

# ---------------------------------------------------------------------------
# Sorting — sort key changes with active persona
# ---------------------------------------------------------------------------
if sort_by == "relevance":
    _sort_key = active_persona
    filtered.sort(
        key=lambda a: (a.get("relevance_scores") or {}).get(_sort_key, 0),
        reverse=True,
    )
elif sort_by == "category":
    filtered.sort(key=lambda a: a.get("primary_category", ""))
else:
    filtered.sort(key=lambda a: a.get("source", ""))

# Show count under the slider
count_placeholder.caption(f"Zobrazeno {len(filtered)} z {len(articles)} článků")
st.markdown("---")

# ---------------------------------------------------------------------------
# Helper: category badge
# ---------------------------------------------------------------------------
def _category_badge(cat: str) -> str:
    bg, label = CATEGORY_COLORS.get(cat, ("#9E9E9E", cat or "?"))
    return (
        f'<span style="background:{bg};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8em;font-weight:600;">{label}</span>'
    )


def _tag_badges(tags: list[str]) -> str:
    parts = []
    for t in tags:
        parts.append(
            f'<span style="background:#424242;color:#ddd;padding:1px 6px;'
            f'border-radius:3px;font-size:0.7em;margin-right:4px;">{t}</span>'
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Article cards
# ---------------------------------------------------------------------------
suffix = "_cs" if lang == "cs" else "_en"

for idx, art in enumerate(filtered):
    headline_key = f"headline{suffix}"
    short_key = f"short{suffix}"
    extended_key = f"extended{suffix}"

    summaries = art.get("summaries") or {}
    headline_text = summaries.get(headline_key, art.get("headline", "Bez titulku"))
    short_text = summaries.get(short_key, "")
    extended_text = summaries.get(extended_key, "")

    cat = art.get("primary_category", "?")
    tags = art.get("secondary_tags") or []
    score = (art.get("relevance_scores") or {}).get(persona, 0)
    source = art.get("source", "?")
    author = art.get("author") or "neuveden"
    art_type = art.get("article_type", "")
    art_id = f"{source}::{art.get('headline', idx)}"

    is_excluded = art_id in st.session_state.excluded_articles

    # Card container
    with st.container():
        # Row 1: badges + score + source
        badge_html = _category_badge(cat)
        if tags:
            badge_html += "  " + _tag_badges(tags)
        badge_html += (
            f'  <span style="color:#FFD54F;font-size:0.85em;">⭐ {score:.1f}</span>'
            f'  <span style="color:#999;font-size:0.8em;">| {source}</span>'
        )
        st.markdown(badge_html, unsafe_allow_html=True)

        # Row 2: headline
        if is_excluded:
            st.markdown(
                f"<h3 style='margin:4px 0;color:#777;text-decoration:line-through;'>"
                f"{headline_text}</h3>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<h3 style='margin:4px 0;'>{headline_text}</h3>",
                unsafe_allow_html=True,
            )

        # Row 3: short summary
        if short_text:
            st.markdown(short_text)

        # Row 4: author | type
        st.caption(f"{author} | {art_type}")

        # Row 5: expander + exclude toggle
        col_exp, col_btn = st.columns([5, 1])
        with col_exp:
            if extended_text:
                with st.expander("Rozšířené shrnutí"):
                    st.markdown(extended_text)
        with col_btn:
            if is_excluded:
                if st.button("Vrátit do briefu", key=f"incl_{idx}"):
                    st.session_state.excluded_articles.discard(art_id)
                    st.rerun()
            else:
                if st.button("Vyřadit z briefu", key=f"excl_{idx}"):
                    st.session_state.excluded_articles.add(art_id)
                    st.rerun()

        st.markdown("---")

# ---------------------------------------------------------------------------
# Sidebar: stats & navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Statistiky")

    included_count = sum(
        1 for a in articles
        if f"{a.get('source', '')}::{a.get('headline', '')}"
        not in st.session_state.excluded_articles
    )
    st.metric("Celkem článků", len(articles))
    st.metric("V briefu", included_count)

    # Category distribution
    st.subheader("Rozložení podle kategorií")
    cat_counts: dict[str, int] = {}
    for a in articles:
        c = a.get("primary_category", "?")
        cat_counts[c] = cat_counts.get(c, 0) + 1

    st.bar_chart(cat_counts)

    st.markdown("---")
    st.page_link("pages/3_Export.py", label="📥 Exportovat brief", icon="📥")
