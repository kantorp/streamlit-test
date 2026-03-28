import streamlit as st

st.set_page_config(
    page_title="Nahrání dokumentů — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# Header
st.title("SHRN.TO")
st.caption("Market Press Intelligence")

st.markdown("---")

# Page context
st.header("📤 Nahrání dokumentů")

st.info(
    "Zde budete moci nahrát PDF, DOCX nebo textové soubory s tiskovými zprávami "
    "a finančními reporty. Nahrané soubory budou zpracovány a připraveny "
    "pro AI analýzu."
)

# Placeholder upload area
st.file_uploader(
    "Vyberte soubory k nahrání",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
    help="Podporované formáty: PDF, DOCX, TXT",
)
