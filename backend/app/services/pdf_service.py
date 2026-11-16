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


def detect_ocr_ambiguities(text: str) -> List[Dict[str, str]]:
    """
    Detects potentially ambiguous OCR tokens relevant to subjects:
    - Proper names / quotes / dates
    - Math signs, exponents, fractions
    - Broken or suspicious symbol sequences
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

    # Check for fraction/exponent/sign patterns that might be inverted or ambiguous in RTL/LTR PDF extraction
    math_matches = re.findall(r"[\d]+[\/÷\^\-\+][\d]+", text)
    if math_matches:
        ambiguities.append(
            {
                "type": "math_symbols_and_fractions",
                "snippet": "، ".join(math_matches[:4]),
                "reason": "تحقق من اتجاه الإشارات والكسور والأسس (LTR) بعد الاستخراج.",
            }
        )

    # Check for dates/years
    date_matches = re.findall(r"\b(?:1\d{3}|20\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b", text)
    if date_matches:
        ambiguities.append(
            {
                "type": "dates_and_chronology",
                "snippet": "، ".join(date_matches[:4]),
                "reason": "تحقق من مطابقة التواريخ والأرقام للمصدر المطبوع.",
            }
        )

    # Check for quotes
    quote_matches = re.findall(r"[«\"]([^»\"]{5,80})[»\"]", text)
    if quote_matches:
        ambiguities.append(
            {
                "type": "quotes_and_attribution",
                "snippet": quote_matches[0][:60],
                "reason": "تحقق من دقة الاقتباس ونسبته وأسماء الأعلام.",
            }
        )

    return ambiguities


def _decode_pdf_literal_string(raw_bytes: bytes) -> str:
    # Handle UTF-16BE BOM if present
    if raw_bytes.startswith(b"\xfe\xff"):
        try:
            return raw_bytes[2:].decode("utf-16-be", errors="ignore")
        except Exception:
            pass
    try:
        return raw_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return raw_bytes.decode("latin-1", errors="ignore")


def _extract_text_from_pdf_stream(stream_data: bytes) -> str:
    chunks: List[str] = []
    # Match literal strings (...) and hex strings <...> inside BT ... ET blocks or stream
    for match in re.finditer(rb"\(([^()\\]*(?:\\.[^()\\]*)*)\)", stream_data):
        raw = match.group(1)
        raw = raw.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\n", b"\n").replace(b"\\r", b"\r")
        txt = _decode_pdf_literal_string(raw).strip()
        if txt:
            chunks.append(txt)

    for match in re.finditer(rb"<([0-9A-Fa-f]{4,})>", stream_data):
        hex_bytes = match.group(1)
        if len(hex_bytes) % 2 == 0:
            try:
                raw = bytes.fromhex(hex_bytes.decode("ascii"))
                txt = _decode_pdf_literal_string(raw).strip()
                if txt and any(ch.isalnum() for ch in txt):
                    chunks.append(txt)
            except Exception:
                pass

    return " ".join(chunks)


def _detect_printed_page_number(page_text: str, fallback_num: int) -> str:
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    if lines:
        for candidate in (lines[-1], lines[0]):
            if re.fullmatch(r"\d{1,4}", candidate):
                return candidate
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
    Extracts real Arabic & bilingual text per page via PyMuPDF (`fitz`) with stream-regex fallback,
    or marks `requires_ocr_or_manual` for scanned pages without fabricating chapters.
    """
    if not file_bytes or len(file_bytes) < 8:
        raise ValueError("الملف المرفوع فارغ أو تالف.")

    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"حجم الملف يتجاوز الحد المسموح به ({MAX_PDF_SIZE_BYTES // (1024 * 1024)} ميجابايت).")

    header_window = file_bytes[:1024]
    if b"%PDF-" not in header_window[:16]:
        raise ValueError("توقيع الملف غير صالح: الملف المرفوع ليس ملف PDF حقيقيًا (%PDF- مفقود).")

    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Extract raw fallback streams so synthetic PDFs work too
    extracted_stream_texts: List[str] = []
    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", file_bytes, re.DOTALL):
        raw_stream = stream_match.group(1)
        decompressed = raw_stream
        try:
            decompressed = zlib.decompress(raw_stream)
        except Exception:
            pass
        txt = _extract_text_from_pdf_stream(decompressed)
        if txt.strip():
            extracted_stream_texts.append(txt.strip())

    fitz_page_texts: List[str] = []
    page_count = 0

    if fitz is not None:
        try:
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                page_count = len(doc)
                if page_count > MAX_PDF_PAGES:
                    raise ValueError(
                        f"عدد صفحات الملف ({page_count}) يتجاوز الحد الأقصى المسموح ({MAX_PDF_PAGES} صفحة)."
                    )
                for idx in range(min(page_count, 100)):
                    page_txt = doc[idx].get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE) or ""
                    page_txt = unicodedata.normalize("NFKC", page_txt).replace("\ufffd", "")
                    fitz_page_texts.append(page_txt)
        except ValueError:
            raise
        except Exception:
            fitz_page_texts = []

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

    for pg_idx in range(1, min(page_count, 100) + 1):
        fitz_txt = fitz_page_texts[pg_idx - 1] if pg_idx - 1 < len(fitz_page_texts) else ""
        stream_txt = extracted_stream_texts[pg_idx - 1] if pg_idx - 1 < len(extracted_stream_texts) else ""
        chosen_txt = fitz_txt if len(fitz_txt.strip()) >= 3 else stream_txt
        chosen_txt = "".join(ch for ch in chosen_txt if ch.isprintable() or ch in "\n\r\t").strip()

        if len(chosen_txt) >= 3:
            has_meaningful_text = True
            needs_ocr = False
        else:
            needs_ocr = True

        printed_num = _detect_printed_page_number(chosen_txt, pg_idx) if chosen_txt else str(pg_idx)
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
