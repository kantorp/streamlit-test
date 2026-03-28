import io

import streamlit as st
import fitz  # PyMuPDF
from docx import Document

from processing.pipeline import _get_api_key, process_documents

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nahrání dokumentů — SHRN.TO",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

KNOWN_TITLES = [
    "Hospodářské noviny",
    "Handelsblatt",
    "Financial Times",
    "Deník N",
]

# Keyword → title mapping (lowercase keywords)
TITLE_KEYWORDS: dict[str, str] = {
    "hospodářské noviny": "Hospodářské noviny",
    "hospodářských novin": "Hospodářské noviny",
    "hn": "Hospodářské noviny",
    "handelsblatt": "Handelsblatt",
    "financial times": "Financial Times",
    "ft": "Financial Times",
    "deník n": "Deník N",
}

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []
if "detected_sources" not in st.session_state:
    st.session_state.detected_sources = {}
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def extract_text_from_pdf(file_bytes: bytes, max_pages: int = 2) -> str:
    """Extract text from the first *max_pages* pages of a PDF."""
    text_parts: list[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_num in range(min(max_pages, len(doc))):
            text_parts.append(doc[page_num].get_text())
    return "\n".join(text_parts)


def extract_text_from_docx(file_bytes: bytes, max_pages: int = 2) -> str:
    """Extract text from a DOCX file (approximate first *max_pages* pages)."""
    doc = Document(io.BytesIO(file_bytes))
    # DOCX has no real concept of pages; use ~3000 chars as a proxy for 2 pages.
    char_limit = max_pages * 3000
    text_parts: list[str] = []
    total = 0
    for para in doc.paragraphs:
        text_parts.append(para.text)
        total += len(para.text)
        if total >= char_limit:
            break
    return "\n".join(text_parts)


def detect_title(text: str) -> str | None:
    """Return recognized newspaper title or None."""
    lower = text.lower()
    for keyword, title in TITLE_KEYWORDS.items():
        if keyword in lower:
            return title
    return None


def format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("SHRN.TO")
st.caption("Market Press Intelligence")
st.markdown("---")
st.header("📤 Nahrání dokumentů")

# ---------------------------------------------------------------------------
# File uploader
# ---------------------------------------------------------------------------
raw_files = st.file_uploader(
    "Přetáhněte soubory sem nebo klikněte pro výběr",
    type=list(ALLOWED_EXTENSIONS),
    accept_multiple_files=True,
    help="Podporované formáty: PDF, DOCX, TXT. Maximální velikost: 50 MB.",
)

# ---------------------------------------------------------------------------
# Validate & process uploaded files
# ---------------------------------------------------------------------------
if raw_files:
    valid_files: list = []
    for f in raw_files:
        if f.size > MAX_FILE_SIZE_BYTES:
            st.error(f"⚠️ Soubor **{f.name}** překračuje limit {MAX_FILE_SIZE_MB} MB a nebyl přijat.")
            continue
        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
        if ext not in ALLOWED_EXTENSIONS:
            st.error(f"⚠️ Nepodporovaný formát souboru: **{f.name}**")
            continue
        valid_files.append(f)

    # Reset state when the set of files changes
    current_names = sorted(f.name for f in valid_files)
    prev_names = sorted(f["name"] for f in st.session_state.uploaded_files)
    if current_names != prev_names:
        st.session_state.uploaded_files = [
            {"name": f.name, "size": f.size, "data": f.getvalue()} for f in valid_files
        ]
        st.session_state.detected_sources = {}
        st.session_state.processing_complete = False

    # -----------------------------------------------------------------------
    # Auto-detect source title
    # -----------------------------------------------------------------------
    for f_info in st.session_state.uploaded_files:
        name = f_info["name"]
        if name in st.session_state.detected_sources:
            continue
        ext = name.rsplit(".", 1)[-1].lower()
        detected: str | None = None
        try:
            if ext == "pdf":
                text = extract_text_from_pdf(f_info["data"])
                detected = detect_title(text)
            elif ext == "docx":
                text = extract_text_from_docx(f_info["data"])
                detected = detect_title(text)
            elif ext == "txt":
                text = f_info["data"].decode("utf-8", errors="replace")[:6000]
                detected = detect_title(text)
        except Exception:
            detected = None

        st.session_state.detected_sources[name] = detected

    # -----------------------------------------------------------------------
    # File list
    # -----------------------------------------------------------------------
    st.subheader("Nahrané soubory")

    files_to_remove: list[str] = []

    for idx, f_info in enumerate(st.session_state.uploaded_files):
        name = f_info["name"]
        size = f_info["size"]
        source = st.session_state.detected_sources.get(name)

        col_name, col_size, col_source, col_action = st.columns([3, 1, 3, 1])

        with col_name:
            st.text(name)
        with col_size:
            st.text(format_size(size))
        with col_source:
            if source:
                st.success(f"✅ {source}")
            else:
                chosen = st.selectbox(
                    "Vyberte titul",
                    options=["— vyberte —"] + KNOWN_TITLES,
                    key=f"source_select_{idx}",
                    label_visibility="collapsed",
                )
                if chosen != "— vyberte —":
                    st.session_state.detected_sources[name] = chosen
        with col_action:
            if st.button("🗑️", key=f"remove_{idx}", help="Odebrat soubor"):
                files_to_remove.append(name)

    # Process removals
    if files_to_remove:
        st.session_state.uploaded_files = [
            f for f in st.session_state.uploaded_files if f["name"] not in files_to_remove
        ]
        for name in files_to_remove:
            st.session_state.detected_sources.pop(name, None)
        st.session_state.processing_complete = False
        st.rerun()

    # -----------------------------------------------------------------------
    # Date picker & process button
    # -----------------------------------------------------------------------
    st.markdown("---")
    pub_date = st.date_input("Datum vydání", value=None, format="DD.MM.YYYY")

    # -----------------------------------------------------------------------
    # API key check
    # -----------------------------------------------------------------------
    api_key = _get_api_key()
    if not api_key:
        st.warning("⚠️ Anthropic API klíč není nastaven. Nastavte proměnnou prostředí "
                    "`ANTHROPIC_API_KEY` nebo ji přidejte do `.streamlit/secrets.toml`.")
        manual_key = st.text_input("Nebo zadejte API klíč zde:", type="password",
                                   key="manual_api_key")
        if manual_key:
            import os
            os.environ["ANTHROPIC_API_KEY"] = manual_key
            api_key = manual_key

    if st.button("🚀 Zpracovat dokumenty", type="primary", disabled=not api_key):
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(pct: float, msg: str) -> None:
            progress_bar.progress(min(pct, 1.0))
            status_text.text(msg)

        try:
            articles = process_documents(
                uploaded_files=st.session_state.uploaded_files,
                sources=st.session_state.detected_sources,
                progress_callback=update_progress,
            )
            st.session_state["articles"] = articles
            st.session_state.processing_complete = True
            st.success(f"✅ Zpracování dokončeno. Nalezeno {len(articles)} článků.")
        except RuntimeError as exc:
            st.error(f"Chyba při zpracování: {exc}")

    # -----------------------------------------------------------------------
    # Post-processing link
    # -----------------------------------------------------------------------
    if st.session_state.processing_complete:
        st.page_link("pages/2_Brief.py", label="📊 Zobrazit brief →", icon="📋")

else:
    # No files uploaded — reset state
    if st.session_state.uploaded_files:
        st.session_state.uploaded_files = []
        st.session_state.detected_sources = {}
        st.session_state.processing_complete = False

    st.info(
        "Nahrajte PDF, DOCX nebo textové soubory s tiskovými zprávami "
        "a finančními reporty. Soubory budou zpracovány a připraveny pro AI analýzu."
    )
