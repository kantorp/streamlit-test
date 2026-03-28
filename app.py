import streamlit as st

st.set_page_config(
    page_title="SHRN.TO — Market Press Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Shared session state initialization
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "brief_data" not in st.session_state:
    st.session_state.brief_data = None
if "export_ready" not in st.session_state:
    st.session_state.export_ready = False

# Header
st.title("SHRN.TO")
st.caption("Market Press Intelligence")

st.markdown("---")

# Landing page description
st.markdown(
    """
    **SHRN.TO** je nástroj pro automatickou analýzu tiskových zpráv a reportů
    z kapitálových trhů. Nahrajte dokumenty, nechte AI vygenerovat stručný brief
    a exportujte výsledky do požadovaného formátu.
    """
)

st.markdown("")

# Three cards linking to subpages
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📤 Nahrání dokumentů")
    st.write(
        "Nahrajte PDF, DOCX nebo textové soubory s tiskovými zprávami "
        "a finančními reporty."
    )
    st.page_link("pages/1_Upload.py", label="Přejít na nahrávání", icon="📤")

with col2:
    st.subheader("📋 Brief")
    st.write(
        "AI analyzuje nahrané dokumenty a vytvoří strukturovaný brief "
        "s klíčovými informacemi."
    )
    st.page_link("pages/2_Brief.py", label="Zobrazit brief", icon="📋")

with col3:
    st.subheader("📥 Export")
    st.write(
        "Exportujte vygenerovaný brief do PDF, DOCX nebo jiného formátu "
        "pro další použití."
    )
    st.page_link("pages/3_Export.py", label="Exportovat", icon="📥")
