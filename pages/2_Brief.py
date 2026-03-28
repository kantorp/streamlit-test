import streamlit as st

st.set_page_config(
    page_title="Brief — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# Header
st.title("SHRN.TO")
st.caption("Market Press Intelligence")

st.markdown("---")

# Page context
st.header("📋 Brief")

st.info(
    "Na této stránce se zobrazí AI-generovaný brief na základě nahraných dokumentů. "
    "Brief bude obsahovat klíčové informace, souhrn tiskových zpráv "
    "a identifikované trendy."
)

# Placeholder content
if st.session_state.get("brief_data"):
    st.write(st.session_state.brief_data)
else:
    st.warning("Zatím nejsou k dispozici žádná data. Nejprve nahrajte dokumenty.")
