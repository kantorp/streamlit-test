import streamlit as st

st.set_page_config(
    page_title="Export — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# Header
st.title("SHRN.TO")
st.caption("Market Press Intelligence")

st.markdown("---")

# Page context
st.header("📥 Export")

st.info(
    "Zde budete moci exportovat vygenerovaný brief do různých formátů — "
    "PDF, DOCX nebo prostý text. Export bude k dispozici po vygenerování briefu."
)

# Placeholder content
if st.session_state.get("export_ready"):
    st.success("Brief je připraven k exportu.")
else:
    st.warning("Zatím není co exportovat. Nejprve vygenerujte brief.")
