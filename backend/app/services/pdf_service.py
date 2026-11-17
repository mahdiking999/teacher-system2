import hashlib
import re
import unicodedata
import zlib
from typing import Dict, Any, List, Optional

try:
    import pymupdf as fitz  # PyMuPDF
except ImportError:
    fitz = None


MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB limit
MAX_PDF_PAGES = 600

_ARABIC_INDIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIACRITIC_TATWEEL_RE = re.compile(r"[\u064B-\u065F\u0670\u0640]")
_VALID_ALT_VERBS = {
    "قالت", "زالت", "نالت", "مالت", "طالت", "جالت", "حالت", "صالت", "بالت", "سالت", "هالت",
    "اختالت", "اغتالت", "انهالت", "استقالت", "استحالت", "استطالت",
    "احالت", "أحالت", "اطالت", "أطالت", "امالت", "أمالت", "ادالت", "أدالت", "انالت", "أنالت", "اسالت", "أسالت",
    "تتالت", "تعالت", "توالت",
}
_INDESIGN_STEM_REPAIRS = (
    (re.compile(r"مشكالت"), "مشكلات"),
    (re.compile(r"معادالت"), "معادلات"),
    (re.compile(r"مدخالت"), "مدخلات"),
    (re.compile(r"عالقة"), "علاقة"),
    (re.compile(r"عالقات"), "علاقات"),
    (re.compile(r"([أإا])ضالع"), r"\1ضلاع"),
    (re.compile(r"([إا])طالق"), r"\1طلاق"),
    (re.compile(r"انطالق"), "انطلاق"),
    (re.compile(r"استهالك"), "استهلاك"),
    (re.compile(r"اختالط"), "اختلاط"),
    (re.compile(r"([اأإ])ختالف"), r"\1ختلاف"),
    (re.compile(r"أقالم"), "أقلام"),
    (re.compile(r"اقالم"), "اقلام"),
    (re.compile(r"غالف"), "غلاف"),
    (re.compile(r"مالبس"), "ملابس"),
    (re.compile(r"مالحظ"), "ملاحظ"),
    (re.compile(r"ثالجة"), "ثلاجة"),
    (re.compile(r"ثالثاء"), "ثلاثاء"),
    (re.compile(r"ميالد"), "ميلاد"),
    (re.compile(r"طالء"), "طلاء"),
    (re.compile(r"داللة"), "دلالة"),
    (re.compile(r"اعاله"), "اعلاه"),
    (re.compile(r"أعاله"), "أعلاه"),
    (re.compile(r"سالميات"), "سلاميات"),
)


def normalize_indesign_arabic_ligatures(text: str) -> str:
    """
    Repairs Adobe InDesign CMap Lam-Alef glyph reversals (e.g. األ -> الأ,
    اإل -> الإ, اآل -> الآ, اال -> الا, المشكالت -> المشكلات) without
    corrupting valid Arabic words such as الأستاذ, الاتحاد, قالت, الثالث,
    بالطريقة, or بالالتزام.
    """
    if not text:
        return text

    # 1. Invalid Arabic orthography: bare Alef + hamzated Alef + Lam -> Lam + hamzated Alef
    text = re.sub(r"ا([أإآ])ل", r"ال\1", text)
    # 2. Word-initial (with optional proclitics) double-Lam-Alef reversal before rule 3
    #    Match genuine اللا- stems so valid الال- stems (الالتزام، الالمنيوم، الالماني، الالكترون) stay untouched
    text = re.sub(
        r"(?<![\u0621-\u064A])([وفبك]{0,2})الال(زم|عب|حق|ئح|ئق|سلك|فت|مع|وع|مر|صق|محد|منته|متناه)",
        r"\1اللا\2",
        text,
    )
    # 3. Word-initial (with optional proclitics و/ف/ب/ك) double bare Alef + Lam
    text = re.sub(r"(?<![\u0621-\u064A])([وفبك]{0,2})اال", r"\1الا", text)
    # 4. Mid/end-word اال before ت (e.g. حاالت -> حالات, مجاالت -> مجالات)
    text = re.sub(r"(?<![موي])االت(?![\u0621-\u064A])", "الات", text)
    # 5. Tanween fath on ال at word end -> لاً (e.g. مثاالً -> مثالاً)
    text = re.sub(r"ال([\u064B])(?![\u0621-\u064A])", r"لا\1", text)

    def _repair_token(match: re.Match) -> str:
        word = match.group(0)
        word_plain = _DIACRITIC_TATWEEL_RE.sub("", word)
        stripped_prefix = re.sub(r"^[وفبكل]", "", word_plain)
        if word_plain in _VALID_ALT_VERBS or stripped_prefix in _VALID_ALT_VERBS:
            return word

        if len(word_plain) >= 5 and re.search(r"الت(?:ها|هم|هن|كما|كم|نا|ه)?$", word_plain):
            if not re.match(r"^(?:[وفبكل]{0,2})الت", word_plain):
                word = re.sub(
                    r"الت((?:[\u064B-\u065F\u0670]*(?:ها|هم|هن|كما|كم|نا|ه))?[\u064B-\u065F\u0670]*)$",
                    r"لات\1",
                    word,
                )

        if len(word_plain) >= 5 and word_plain.endswith("الن") and not re.match(r"^(?:[وفبكل]{0,2})الن$", word_plain):
            word = re.sub(r"الن([\u064B-\u065F\u0670]*)$", r"لان\1", word)

        for pat, rep in _INDESIGN_STEM_REPAIRS:
            word = pat.sub(rep, word)
        word = re.sub(r"(^|[وفبكس]*)([نتي])الحظ", r"\1\2لاحظ", word)
        word = re.sub(r"^([وفبكل]{0,2})بالط(ة|ات)?$", r"\1بلاط\2", word)
        return word

    return re.sub(r"[\u0621-\u065F\u0670\u0640]+", _repair_token, text)


def detect_ocr_ambiguities(text: str) -> List[Dict[str, str]]:
    """
    Detects potentially ambiguous OCR tokens relevant to subjects:
    - Scanned / empty page needing OCR
    - Genuine math fractions, operators, roots, malformed LaTeX / broken operators
      (ignoring hyphenated lesson codes like 1-1, [1-4], and plain years/integers)
    - Scrambled / mixed-script date tokens
    - Single-line quoted passages / attributions
    """
    ambiguities: List[Dict[str, str]] = []
    if not text or not text.strip():
        return [
            {
                "type": "scanned_or_empty_page",
                "snippet": "صفحة خالية من طبقة نصية",
                "reason": "يتطلب OCR أو تفريغًا يدويًا ومراجعة بشرية للنص والأعلام والمعادلات.",
            }
        ]

    # Strip URLs, calendar dates, and year spans (e.g. 2025/2026) before math detection
    math_scan_text = re.sub(r"https?://\S+", " ", text)
    math_scan_text = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", " ", math_scan_text)
    math_scan_text = re.sub(r"\b(?:1[489]\d{2}|20\d{2})\s*/\s*(?:1[489]\d{2}|20\d{2})\b", " ", math_scan_text)

    math_patterns = (
        # Genuine numeric or single-letter-variable fractions (ignores 1-1 codes and word/word like and/or)
        r"(?<![\da-zA-Z/])(?:[0-9\u0660-\u0669]+|[a-zA-Z])\s*/\s*(?:[0-9\u0660-\u0669]+|[a-zA-Z])(?![\da-zA-Z/])",
        # Binary math operators / exponents / inequalities
        r"(?:[\d\u0660-\u0669a-zA-Z\.\)\]]+)\s*[×÷\^\u2212≤≥≠±]\s*(?:-?[\d\u0660-\u0669a-zA-Z\.\(\[]+)",
        # Equations (=) and explicit addition between operands
        r"(?:[\d\u0660-\u0669a-zA-Z\.\)\]]+)\s*[=+]\s*(?:[-+.\d\u0660-\u0669a-zA-Z\(\[]+)",
        # Radicals & mathematical pi
        r"[√∛]\s*[\da-zA-Z\(\[]",
        r"π",
        # Raw or potentially malformed LaTeX math tokens
        r"\\(?:frac|sqrt|times|div|pm|leq|geq|neq|pi)\b",
        # Broken math operators adjacent to punctuation / garbage or dangling ^/_
        r"(?:[×÷\^√∛]\s*[^\w\d\s\(\[\-\+\.]|[^\w\d\s\)\]]\s*[×÷\^√∛])",
        r"[\^_]\s*(?:$|\s)",
    )
    math_matches: List[str] = []
    for mp in math_patterns:
        for m in re.finditer(mp, math_scan_text):
            snippet = m.group(0).strip()
            if snippet and snippet not in math_matches:
                math_matches.append(snippet)
            if len(math_matches) >= 4:
                break
        if len(math_matches) >= 4:
            break

    if math_matches:
        ambiguities.append(
            {
                "type": "math_symbols_and_fractions",
                "snippet": "، ".join(math_matches[:4]),
                "reason": "تحقق من اتجاه الإشارات والكسور والأسس (LTR) بعد الاستخراج.",
            }
        )

    # Flag only scrambled, mixed-script, or malformed Hijri/Gregorian date tokens (not plain integers like 1000 or 2025)
    date_matches = re.findall(
        r"(?:[0-9]+[\u0660-\u0669]+|[\u0660-\u0669]+[0-9]+|(?<![\u0621-\u064A])م[ \t]*(?:1[489]|20|١[٤٨٩]|٢٠)[\d\u0660-\u0669]{2}|[\d\u0660-\u0669]{2,4}[ \t]*هـ[ \t]*[\d\u0660-\u0669]+)",
        text,
    )
    if date_matches:
        ambiguities.append(
            {
                "type": "dates_and_chronology",
                "snippet": "، ".join(date_matches[:4]),
                "reason": "تحقق من مطابقة التواريخ والأرقام للمصدر المطبوع.",
            }
        )

    # Check for single-line quotes
    quote_matches = re.findall(r'[«"]([^»"\n]{5,80})[»"]', text)
    if quote_matches:
        ambiguities.append(
            {
                "type": "quotes_and_attribution",
                "snippet": quote_matches[0][:60],
                "reason": "تحقق من دقة الاقتباس ونسبته وأسماء الأعلام.",
            }
        )

    return ambiguities


_NON_TEXT_STREAM_DICT_RE = re.compile(
    rb"/(?:Subtype\s*/(?:Image|Type1C|CIDFontType0C|OpenType)|"
    rb"Type\s*/(?:Metadata|XRef|ObjStm)|"
    rb"Filter\s*(?:\[\s*)?/(?:DCTDecode|JPXDecode|CCITTFaxDecode|JBIG2Decode)|"
    rb"BitsPerComponent\b|"
    rb"Length1\b)"
)
_READABLE_SCRIPT_CHAR_RE = re.compile(r"[A-Za-z0-9\u0621-\u064A\u0660-\u0669\u0671-\u06D3]")
_READABLE_WORD_RE = re.compile(r"[A-Za-z\u0621-\u064A\u0671-\u06D3]{2,}")


def _is_valid_extracted_chunk(txt: str) -> bool:
    if not txt or "\ufffd" in txt:
        return False
    # Reject C0/C1 control characters other than normal whitespace
    for ch in txt:
        code = ord(ch)
        if (code < 32 and ch not in "\n\r\t") or (0x7F <= code <= 0x9F):
            return False
    non_ws = [ch for ch in txt if not ch.isspace()]
    if len(non_ws) < 2:
        return False
    script_count = sum(1 for ch in non_ws if _READABLE_SCRIPT_CHAR_RE.match(ch))
    if (script_count / len(non_ws)) < 0.6:
        return False
    return bool(_READABLE_WORD_RE.search(txt))


def _decode_pdf_literal_string(raw_bytes: bytes) -> str:
    # Handle UTF-16BE BOM if present
    if raw_bytes.startswith(b"\xfe\xff"):
        try:
            return raw_bytes[2:].decode("utf-16-be", errors="strict")
        except Exception:
            return ""
    try:
        return raw_bytes.decode("utf-8", errors="strict")
    except Exception:
        # Only allow pure printable ASCII/Latin-1 PDF literal text, never arbitrary high bytes
        if all((32 <= b <= 126) or b in (9, 10, 13) for b in raw_bytes):
            return raw_bytes.decode("latin-1", errors="ignore")
        return ""


def _extract_text_from_pdf_stream(stream_data: bytes) -> str:
    if not stream_data:
        return ""

    # Reject raw binary / image / font streams immediately
    sample = stream_data[:2048]
    non_printable = sum(1 for b in sample if b < 9 or (14 <= b <= 31) or b >= 127)
    has_bt_et = b"BT" in stream_data and b"ET" in stream_data
    if not has_bt_et and (non_printable / max(1, len(sample))) > 0.25:
        return ""

    bt_blocks = re.findall(rb"\bBT\b(.*?)\bET\b", stream_data, re.DOTALL) if has_bt_et else [stream_data]
    chunks: List[str] = []
    for block in bt_blocks:
        for match in re.finditer(rb"\(([^()\\]*(?:\\.[^()\\]*)*)\)", block):
            raw = match.group(1)
            raw = raw.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\n", b"\n").replace(b"\\r", b"\r")
            txt = _decode_pdf_literal_string(raw).strip()
            if _is_valid_extracted_chunk(txt):
                chunks.append(txt)

        for match in re.finditer(rb"<([0-9A-Fa-f]{4,})>", block):
            hex_bytes = match.group(1)
            if len(hex_bytes) % 2 == 0:
                try:
                    raw = bytes.fromhex(hex_bytes.decode("ascii"))
                    txt = _decode_pdf_literal_string(raw).strip()
                    if _is_valid_extracted_chunk(txt):
                        chunks.append(txt)
                except Exception:
                    pass

    return " ".join(chunks)


def _clean_page_number_candidate(line: str) -> str:
    cleaned = unicodedata.normalize("NFKC", line).translate(_ARABIC_INDIC_DIGIT_MAP)
    cleaned = _DIACRITIC_TATWEEL_RE.sub("", cleaned)
    cleaned = re.sub(r"^(?:صفحة|صفحه|page|p\.?|ص)\s*[:\.\-]?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\s\-\[\]\(\)«»|•·.,:]+|[\s\-\[\]\(\)«»|•·.,:]+$", "", cleaned)
    return cleaned.strip()


def _detect_printed_page_number(page_text: str, fallback_num: int, total_pages: Optional[int] = None) -> str:
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    if not lines:
        return str(fallback_num)

    # Check header (first 2 lines) before footer (last 2 lines)
    header_candidates = lines[:2]
    footer_candidates = list(reversed(lines[-2:]))
    candidates: List[tuple[str, bool]] = [(c, False) for c in header_candidates] + [
        (c, True) for c in footer_candidates
    ]

    cover_keywords = ("وزارة التربية", "للصف", "الطبعة", "تنقيح", "المديرية العامة للمناهج", "تأليف")
    is_cover_like = fallback_num == 1 and any(kw in page_text for kw in cover_keywords)

    for raw_cand, is_footer in candidates:
        cleaned = _clean_page_number_candidate(raw_cand)
        if not re.fullmatch(r"\d{1,4}", cleaned):
            continue
        val = int(cleaned)
        if val < 1:
            continue
        # Reject Gregorian/Hijri year numbers unless document genuinely has >= that many pages
        if val >= 1350 and (total_pages is None or total_pages < val):
            continue
        if total_pages is not None and total_pages > 0 and val > total_pages + 20:
            continue
        # Reject cover footer metadata such as grade number (e.g. "8" under "للصف الثاني المتوسط")
        if is_cover_like and is_footer and val != 1:
            continue
        return str(val)

    return str(fallback_num)


def render_pdf_page_to_png_bytes(file_bytes: bytes, pdf_page_number: int, dpi: int = 150) -> Optional[bytes]:
    """
    Renders a single PDF page (1-indexed) to PNG bytes via PyMuPDF for Vision OCR.
    Returns None if PyMuPDF is unavailable or rendering fails.
    """
    if fitz is None or not file_bytes or pdf_page_number < 1:
        return None
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            if pdf_page_number > len(doc):
                return None
            page = doc[pdf_page_number - 1]
            pix = page.get_pixmap(dpi=dpi)
            return pix.tobytes("png")
    except Exception:
        return None


def inspect_and_extract_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Validates actual PDF magic signature (%PDF-), size limits, and page count.
    Extracts real Arabic & bilingual text per page via PyMuPDF (`fitz`) with stream-regex fallback
    only when PyMuPDF is unavailable or yields 0 pages on minimal synthetic stubs,
    or marks `requires_ocr_or_manual` for scanned pages without fabricating text or leaking binary bytes.
    """
    if not file_bytes or len(file_bytes) < 8:
        raise ValueError("الملف المرفوع فارغ أو تالف.")

    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"حجم الملف يتجاوز الحد المسموح به ({MAX_PDF_SIZE_BYTES // (1024 * 1024)} ميجابايت).")

    header_window = file_bytes[:1024]
    if b"%PDF-" not in header_window[:16]:
        raise ValueError("توقيع الملف غير صالح: الملف المرفوع ليس ملف PDF حقيقيًا (%PDF- مفقود).")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    fitz_page_texts: Optional[List[str]] = None
    page_count = 0

    if fitz is not None:
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                page_count = len(doc)
                if page_count > MAX_PDF_PAGES:
                    raise ValueError(
                        f"عدد صفحات الملف ({page_count}) يتجاوز الحد الأقصى المسموح ({MAX_PDF_PAGES} صفحة)."
                    )
                if page_count >= 1:
                    fitz_page_texts = []
                    for idx in range(page_count):
                        page_txt = doc[idx].get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE) or ""
                        page_txt = unicodedata.normalize("NFKC", page_txt).replace("\ufffd", "")
                        page_txt = normalize_indesign_arabic_ligatures(page_txt)
                        fitz_page_texts.append(page_txt)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("ملف PDF تالف أو غير قابل للقراءة.") from exc

    extracted_stream_texts: List[str] = []
    if fitz_page_texts is None:
        # Fallback stream scan only when PyMuPDF is unavailable or opened a 0-page minimal stub
        for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", file_bytes, re.DOTALL):
            dict_window = file_bytes[max(0, stream_match.start() - 600) : stream_match.start()]
            if _NON_TEXT_STREAM_DICT_RE.search(dict_window):
                continue
            raw_stream = stream_match.group(1)
            decompressed = raw_stream
            try:
                decompressed = zlib.decompress(raw_stream)
            except Exception:
                pass
            txt = _extract_text_from_pdf_stream(decompressed)
            if txt.strip():
                extracted_stream_texts.append(normalize_indesign_arabic_ligatures(txt.strip()))

    if page_count == 0:
        page_matches = re.findall(rb"/Type\s*/Page\b(?!s)", file_bytes)
        page_count = len(page_matches)
        if page_count == 0:
            count_matches = re.findall(rb"/Count\s+(\d+)", file_bytes)
            page_count = max(int(c) for c in count_matches) if count_matches else 1
        if page_count > MAX_PDF_PAGES:
            raise ValueError(f"عدد صفحات الملف ({page_count}) يتجاوز الحد الأقصى المسموح ({MAX_PDF_PAGES} صفحة).")

    pages_result: List[Dict[str, Any]] = []
    has_meaningful_text = False

    for pg_idx in range(1, min(page_count, MAX_PDF_PAGES) + 1):
        if fitz_page_texts is not None:
            chosen_txt = fitz_page_texts[pg_idx - 1]
        else:
            chosen_txt = extracted_stream_texts[pg_idx - 1] if pg_idx - 1 < len(extracted_stream_texts) else ""

        chosen_txt = "".join(ch for ch in chosen_txt if ch.isprintable() or ch in "\n\r\t").strip()

        if len(chosen_txt) >= 3:
            has_meaningful_text = True
            needs_ocr = False
        else:
            chosen_txt = ""
            needs_ocr = True

        printed_num = _detect_printed_page_number(chosen_txt, pg_idx, total_pages=page_count) if chosen_txt else str(pg_idx)
        ambiguities = detect_ocr_ambiguities(chosen_txt)
        pages_result.append(
            {
                "pdfPageNumber": pg_idx,
                "printedPageNumber": printed_num,
                "extractedText": chosen_txt,
                "correctedText": chosen_txt,
                "needsOcrReview": needs_ocr or len(ambiguities) > 0,
                "ocrAmbiguities": ambiguities,
                "humanReviewed": False,
            }
        )

    extraction_status = "extracted_text" if has_meaningful_text else "requires_ocr_or_manual"

    return {
        "sha256Fingerprint": sha256_hash,
        "fileSize": len(file_bytes),
        "pageCount": page_count,
        "extractionStatus": extraction_status,
        "pages": pages_result,
    }
