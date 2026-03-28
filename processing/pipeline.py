"""
Document processing pipeline for SHRN.TO.

Extracts text from PDF/DOCX/TXT, segments into articles via Claude API,
classifies and summarizes each article.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from typing import Callable

# ---------------------------------------------------------------------------
# Force UTF-8 for the entire process — fixes 'ascii' codec errors on macOS
# and in Docker containers where locale defaults to C/POSIX.
# ---------------------------------------------------------------------------
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF
import streamlit as st
from anthropic import Anthropic
from docx import Document

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "claude-sonnet-4-20250514"

SECONDARY_TAGS = [
    "finance", "energetika", "automotive", "real-estate", "technologie",
    "zdravotnictví", "telekomunikace", "průmysl", "M&A", "IPO", "regulace",
    "makro-data", "měnová-politika", "ESG", "AI", "digitalizace", "korupce",
    "volby", "personální-změna", "komentář",
    "CZ", "SK", "DE", "EU", "USA", "UK", "global",
]


# ---------------------------------------------------------------------------
# Unicode helpers
# ---------------------------------------------------------------------------
def _normalize_text(text: str) -> str:
    """Normalize Unicode text to NFC form and strip null bytes."""
    text = text.replace("\x00", "")
    return unicodedata.normalize("NFC", text)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
def _get_api_key() -> str | None:
    """Retrieve Anthropic API key from env or Streamlit secrets."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        pass
    return key


def _get_client() -> Anthropic:
    key = _get_api_key()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
    return Anthropic(api_key=key)


def _call_claude(
    client: Anthropic,
    system_prompt: str,
    user_text: str,
    max_tokens: int = 4096,
) -> str:
    """Call Claude API with system prompt and user text separated.

    Uses the system parameter for instructions and user message for content.
    Both strings are sanitized through UTF-8 encode/decode cycle.
    """
    clean_system = system_prompt.encode("utf-8", errors="replace").decode("utf-8")
    clean_user = user_text.encode("utf-8", errors="replace").decode("utf-8")
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=clean_system,
        messages=[{"role": "user", "content": clean_user}],
    )
    return response.content[0].text.strip()


def _parse_json_response(raw: str) -> dict | list:
    """Parse JSON from Claude response with progressive fallbacks.

    1. Try direct json.loads (after stripping markdown fences).
    2. Extract the substring between the first '[' / '{' and last ']' / '}'.
    3. Fix common issues (trailing commas) and retry.
    """
    # Strip markdown fences
    cleaned = raw
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    # --- Attempt 1: direct parse ---
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # --- Attempt 2: extract outermost JSON structure from raw text ---
    # Find the first [ or { and last ] or }
    first_bracket = None
    last_bracket = None
    open_char = None
    for i, ch in enumerate(raw):
        if ch in ("[", "{"):
            first_bracket = i
            open_char = ch
            break
    if open_char is not None:
        close_char = "]" if open_char == "[" else "}"
        last_bracket = raw.rfind(close_char)

    if first_bracket is not None and last_bracket is not None and last_bracket > first_bracket:
        substring = raw[first_bracket : last_bracket + 1]
        try:
            return json.loads(substring)
        except json.JSONDecodeError:
            pass

        # --- Attempt 3: fix trailing commas and retry ---
        fixed = re.sub(r",\s*([}\]])", r"\1", substring)
        return json.loads(fixed)

    # Nothing worked — raise with the original text for debugging
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# 1. Text extraction
# ---------------------------------------------------------------------------
def extract_text(file_bytes: bytes, file_type: str) -> str:
    """Extract full text from a document.

    Args:
        file_bytes: Raw file content.
        file_type: One of 'pdf', 'docx', 'txt'.

    Returns:
        Extracted text as a single string.
    """
    file_type = file_type.lower()

    if file_type == "pdf":
        parts: list[str] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text("text")
                parts.append(_normalize_text(page_text))
        return "\n".join(parts)

    if file_type == "docx":
        doc = Document(io.BytesIO(file_bytes))
        return _normalize_text("\n".join(para.text for para in doc.paragraphs))

    if file_type == "txt":
        return _normalize_text(file_bytes.decode("utf-8", errors="replace"))

    raise ValueError(f"Unsupported file type: {file_type}")


# ---------------------------------------------------------------------------
# 2. Article segmentation
# ---------------------------------------------------------------------------
CHUNK_MAX_CHARS = 25_000


def segment_articles_from_docx(full_text: str, source_name: str) -> list[dict]:
    """Split DOCX text into articles using structural delimiters.

    Recognizes two delimiter patterns:
    - A line of 20+ dashes (e.g. 50× '─' or '-')
    - Section headers like ``[Ekonomika] zpráva | str. 5``

    From each block extracts headline, author, full_text, article_type.
    """
    # Split by lines of 20+ dashes (ASCII or Unicode dash)
    blocks = re.split(r'\r?\n[\-─]{20,}\r?\n', full_text)

    # If only one block, try splitting by section headers
    if len(blocks) <= 1:
        header_re = re.compile(r'(\[.+?\]\s+.+?\|.*?str\.[^\n]*)', re.MULTILINE)
        parts = header_re.split(full_text)
        # parts = [before_first_header, header1, body1, header2, body2, ...]
        if len(parts) > 2:
            blocks = []
            for j in range(1, len(parts), 2):
                header = parts[j]
                body = parts[j + 1] if j + 1 < len(parts) else ""
                blocks.append(header + "\n" + body)

    articles: list[dict] = []
    for block in blocks:
        block = block.strip()
        if not block or len(block) < 30:
            continue

        # Check for section header at the start
        section_match = re.match(r'^\[(.+?)\]\s+(.+?)\s*\|', block)
        article_type = "zpráva"
        if section_match:
            article_type = section_match.group(2).strip()
            # Remove the section header line
            nl = block.find('\n')
            block = block[nl + 1:].strip() if nl != -1 else block

        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines:
            continue

        headline = lines[0]

        # Try to find author in first few lines
        author = None
        for line in lines[1:5]:
            m = re.match(
                r'^(?:autor[:\s]+|od\s+|napsal[a]?\s+)(.+)',
                line,
                re.IGNORECASE,
            )
            if m:
                author = m.group(1).strip()
                break

        articles.append({
            "headline": _normalize_text(headline),
            "author": _normalize_text(author) if author else None,
            "full_text": _normalize_text(block),
            "article_type": _normalize_text(article_type),
            "source": source_name,
        })

    print(f"DOCX segmentace: nalezeno {len(articles)} článků z '{source_name}'")
    return articles


def _split_into_chunks(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Split *text* into chunks of at most *max_chars* characters.

    Tries to break on the last newline before the limit so articles are not
    split mid-sentence where possible.
    """
    chunks: list[str] = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        # Try to split at the last newline within the limit
        split_pos = text.rfind("\n", 0, max_chars)
        if split_pos == -1:
            split_pos = max_chars
        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    return chunks


def segment_articles(
    full_text: str,
    source_name: str,
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """Use Claude to split raw text into individual articles.

    Long texts are split into chunks of up to CHUNK_MAX_CHARS characters and
    each chunk is processed by a separate API call with a short sleep in
    between to respect rate limits.
    """
    print(f"Text length: {len(full_text)} chars, encoding check OK")

    client = _get_client()

    system_prompt = (
        "Jsi expert na analýzu novinových textů. Dostaneš surový text extrahovaný "
        "z novinové repliky \"" + source_name + "\". "
        "Identifikuj jednotlivé články a pro každý vrať JSON objekt s těmito poli: "
        "\"headline\" (titulek článku), "
        "\"author\" (autor článku, nebo null pokud není uveden), "
        "\"full_text\" (celý text článku), "
        "\"article_type\" (jeden z: zpráva, komentář, rozhovor, analýza, editorial, krátká-zpráva). "
        "Ignoruj reklamy, inzeráty, TV programy, křížovky a jiný neredakční obsah.\n\n"
        "CRITICAL: Return ONLY a valid JSON array. No trailing commas. No comments. "
        "No text before or after the JSON. Ensure all strings are properly escaped "
        "with backslashes for quotes and newlines."
    )

    chunks = _split_into_chunks(full_text)
    total_chunks = len(chunks)
    all_articles: list[dict] = []
    failed_chunks: list[int] = []

    for idx, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(idx / total_chunks, f"Segmentuji články (část {idx}/{total_chunks})...")

        try:
            raw = _call_claude(client, system_prompt, chunk, max_tokens=8192)
            articles = _parse_json_response(raw)
        except Exception as exc:
            print(f"WARNING: Chunk {idx}/{total_chunks} selhal: {exc}")
            failed_chunks.append(idx)
            if idx < total_chunks:
                time.sleep(2)
            continue

        # Normalize all text fields and tag with source
        for art in articles:
            art["source"] = source_name
            for key in ("headline", "author", "full_text", "article_type"):
                if isinstance(art.get(key), str):
                    art[key] = _normalize_text(art[key])

        all_articles.extend(articles)

        # Rate-limit pause between chunks (skip after the last one)
        if idx < total_chunks:
            time.sleep(2)

    ok_count = total_chunks - len(failed_chunks)
    print(f"Segmentace dokončena: {ok_count}/{total_chunks} chunků úspěšně zpracováno.")
    if failed_chunks:
        print(f"Selhané chunky: {failed_chunks}")

    return all_articles


# ---------------------------------------------------------------------------
# 3 & 4. Classification + Summarization (combined to save tokens)
# ---------------------------------------------------------------------------
def _first_sentences(text: str, count: int = 2) -> str:
    """Return the first *count* sentences from *text*."""
    sentences: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentences.append(part)
        if len(sentences) >= count:
            break
    return " ".join(sentences)


def _first_paragraph(text: str) -> str:
    """Return the first non-empty paragraph from *text*."""
    for para in text.split("\n\n"):
        para = para.strip()
        if para:
            return para
    return text[:800]


def _apply_fallback_summaries(article: dict) -> None:
    """Fill article with default classification and text-derived summaries."""
    headline = article.get("headline", "Bez titulku")
    full_text = article.get("full_text", "")

    article["primary_category"] = "UNKNOWN"
    article["secondary_tags"] = []
    article["relevance_scores"] = {
        "investment_professional": 3.0,
        "decision_maker": 3.0,
    }

    short = _first_sentences(full_text, 2)
    extended = _first_paragraph(full_text)

    article["summaries"] = {
        "headline_cs": headline,
        "headline_en": headline,
        "short_cs": short,
        "short_en": short,
        "extended_cs": extended,
        "extended_en": extended,
    }


def classify_and_summarize(article: dict) -> bool:
    """Classify and summarize a single article in one API call.

    Returns True on success. On failure applies fallback values derived from
    the article text so the article is always usable downstream.
    """
    client = _get_client()

    tags_str = ", ".join(SECONDARY_TAGS)
    headline = article.get("headline", "")
    text = article.get("full_text", "")

    system_prompt = (
        "Jsi analytik zaměřený na finanční a ekonomické zpravodajství. "
        "Dostaneš novinový článek. Proveď dvě úlohy najednou:\n\n"
        "ÚLOHA 1 - Klasifikace:\n"
        "- \"primary_category\": jedna z: ECON, POL_CZ, POL_INT, REG\n"
        "- \"secondary_tags\": 1-3 tagy z tohoto seznamu: " + tags_str + "\n"
        "- \"relevance_scores\": objekt s klíči \"investment_professional\" (float 1-5) "
        "a \"decision_maker\" (float 1-5)\n\n"
        "ÚLOHA 2 - Shrnutí:\n"
        "- \"headline_cs\": titulek česky, max 15 slov\n"
        "- \"headline_en\": headline in English, max 15 words\n"
        "- \"short_cs\": 250-350 znaků, česky, 2-3 věty, vlastními slovy\n"
        "- \"short_en\": 250-350 characters, English, 2-3 sentences, in your own words\n"
        "- \"extended_cs\": 600-800 znaků, česky, na konci přidej: "
        "\"📈 Implikace: ...\" (pro investičního profesionála) a "
        "\"📌 Klíčový takeaway: ...\" (pro rozhodovatele)\n"
        "- \"extended_en\": 600-800 characters, English, at the end add: "
        "\"📈 Implications: ...\" (for investment professional) and "
        "\"📌 Key takeaway: ...\" (for decision maker)\n\n"
        "Instrukce: VŽDY vlastními slovy, nikdy přímá citace. "
        "Zachovat věcnou přesnost. Uvést klíčová čísla a jména.\n\n"
        "CRITICAL: Return ONLY valid JSON. No trailing commas. "
        "Ensure all string values are properly escaped — use backslash "
        "before any quotes or newlines inside strings.\n\n"
        "Vrať POUZE validní JSON objekt s klíči: primary_category, secondary_tags, "
        "relevance_scores, headline_cs, headline_en, short_cs, short_en, "
        "extended_cs, extended_en. Bez dalšího textu."
    )

    user_text = "Titulek: " + headline + "\n\nText: " + text

    try:
        raw = _call_claude(client, system_prompt, user_text, max_tokens=4096)
        result = _parse_json_response(raw)
    except Exception as exc:
        print(f"WARNING: Klasifikace článku '{headline}' selhala, použity default hodnoty: {exc}")
        _apply_fallback_summaries(article)
        return False

    # Merge classification fields into article
    article["primary_category"] = result.get("primary_category")
    article["secondary_tags"] = result.get("secondary_tags", [])
    article["relevance_scores"] = result.get("relevance_scores", {})

    # Merge summaries into article — normalize all string values
    article["summaries"] = {}
    for key in ("headline_cs", "headline_en", "short_cs", "short_en",
                "extended_cs", "extended_en"):
        val = result.get(key, "")
        article["summaries"][key] = _normalize_text(val) if isinstance(val, str) else val

    return True


# ---------------------------------------------------------------------------
# 5. Orchestration
# ---------------------------------------------------------------------------
def process_documents(
    uploaded_files: list[dict],
    sources: dict[str, str],
    progress_callback: Callable[[float, str], None] | None = None,
) -> list[dict]:
    """Run the full pipeline on all uploaded documents.

    Args:
        uploaded_files: List of dicts with keys 'name', 'size', 'data'.
        sources: Mapping of filename -> detected source title.
        progress_callback: Optional callback(progress_float, status_text).

    Returns:
        List of fully enriched article dicts.
    """

    def _update(pct: float, msg: str) -> None:
        if progress_callback:
            progress_callback(pct, msg)

    try:
        total_files = len(uploaded_files)
        all_articles: list[dict] = []

        # --- Phase 1: Extract text from all documents ---
        texts: list[tuple[str, str, str]] = []  # (source_name, full_text, file_ext)
        for i, f_info in enumerate(uploaded_files, 1):
            name = f_info["name"]
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            source_name = sources.get(name, name)

            _update(
                0.1 * (i / total_files),
                f"Extrahuji text (dokument {i}/{total_files}): {name}...",
            )

            text = extract_text(f_info["data"], ext)
            texts.append((source_name, text, ext))

        # --- Phase 2: Segment articles in each document ---
        for i, (source_name, text, ext) in enumerate(texts, 1):
            base_pct = 0.1 + 0.3 * ((i - 1) / len(texts))
            doc_pct_range = 0.3 / len(texts)

            def _seg_progress(chunk_pct: float, msg: str, _base=base_pct, _range=doc_pct_range) -> None:
                _update(_base + _range * chunk_pct, f"{source_name}: {msg}")

            _update(base_pct, f"Segmentuji články (dokument {i}/{len(texts)}): {source_name}...")

            if ext == "docx":
                articles = segment_articles_from_docx(text, source_name)
            else:
                articles = segment_articles(text, source_name, progress_callback=_seg_progress)
            all_articles.extend(articles)

        # --- Phase 3: Classify & summarize each article ---
        total_articles = len(all_articles)
        if total_articles == 0:
            _update(1.0, "Nebyly nalezeny žádné články.")
            return []

        failed_articles: list[str] = []
        for i, article in enumerate(all_articles, 1):
            _update(
                0.4 + 0.6 * (i / total_articles),
                f"Klasifikuji a sumarizuji článek {i}/{total_articles}...",
            )
            ok = classify_and_summarize(article)
            if not ok:
                failed_articles.append(article.get("headline", f"článek #{i}"))
            # Rate-limit pause (skip after the last one)
            if i < total_articles:
                time.sleep(2)

        if failed_articles:
            print(
                f"Klasifikace dokončena: {total_articles - len(failed_articles)}/{total_articles} "
                f"článků úspěšně (selhané mají default hodnoty): {failed_articles}"
            )

        _update(1.0, "Hotovo!")
        return all_articles

    except Exception:
        traceback.print_exc()
        raise
