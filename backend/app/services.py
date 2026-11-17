from functools import lru_cache
from datetime import timezone
from io import BytesIO
from xml.sax.saxutils import escape

import pymupdf as fitz
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .detection import DISCLAIMER


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_page(page) -> str:
    try:
        engine = _ocr_engine()
    except (ImportError, OSError, RuntimeError) as exc:
        raise ValueError(
            "OCR is unavailable. Install rapidocr-onnxruntime and restart the backend."
        ) from exc

    scale = min(2.0, 2400 / max(page.rect.width, page.rect.height))
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        colorspace=fitz.csRGB,
        alpha=False,
    )
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    bgr_image = image[:, :, :3][:, :, ::-1].copy()
    try:
        result, _ = engine(bgr_image)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("OCR could not process a scanned PDF page.") from exc
    if not result:
        return ""
    return "\n".join(
        str(line[1]).strip()
        for line in result
        if len(line) > 1 and str(line[1]).strip()
    )


def extract_pdf_document(contents: bytes) -> tuple[str, dict]:
    if len(contents) > 10 * 1024 * 1024:
        raise ValueError("PDF exceeds the 10 MB upload limit.")
    try:
        with fitz.open(stream=contents, filetype="pdf") as document:
            if document.page_count > 100:
                raise ValueError("PDF exceeds the 100-page processing limit.")
            parts = []
            text_pages = 0
            ocr_pages = 0
            for page in document:
                page_text = page.get_text("text").strip()
                if len(page_text) >= 40:
                    parts.append(page_text)
                    text_pages += 1
                    continue
                if page_text:
                    parts.append(page_text)
                recovered = _ocr_page(page)
                if recovered:
                    parts.append(recovered)
                    ocr_pages += 1
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError("The uploaded file could not be read as a valid PDF.") from exc
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("The PDF page could not be rendered for text extraction.") from exc

    text = "\n".join(parts)
    if len(text.strip()) < 40:
        raise ValueError(
            "No readable text was recovered. Scanned/image-only content may be too faint or unreadable."
        )
    mode = "mixed" if text_pages and ocr_pages else ("ocr" if ocr_pages else "text")
    return text[:30000], {
        "mode": mode,
        "text_pages": text_pages,
        "ocr_pages": ocr_pages,
    }


def extract_pdf_text(contents: bytes) -> str:
    return extract_pdf_document(contents)[0]


def make_report(scan) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    story = [
        Paragraph("InternGuard", styles["Title"]),
        Paragraph("Preliminary Opportunity Risk Report", styles["Heading2"]),
        Spacer(1, 10),
    ]
    extracted = scan.details.get("extracted_details")
    if extracted:
        story.append(Paragraph("Extracted offer details", styles["Heading2"]))
        for label, key in [("Company", "company"), ("Job title", "job_title"), ("Salary", "salary")]:
            story.append(Paragraph(f"<b>{label}:</b> {escape(str(extracted.get(key, 'Not identified')))}", styles["BodyText"]))
        story.append(Spacer(1, 8))
    created = scan.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    metadata = [
        ["Scan ID", str(scan.id)],
        ["Timestamp (UTC)", created.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
        ["Opportunity", scan.job_title or "Not identified"],
        ["Company", scan.company_name or "Not provided"],
        ["Scan type", scan.scan_type],
        ["Data type", "Illustrative sample" if scan.details.get("sample_data") else "User scan"],
        ["Risk score", f"{scan.risk_score}/100 — {scan.risk_category} RISK"],
        ["Summary", scan.summary],
    ]
    table = Table(metadata, colWidths=[120, 390])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2937")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe3ec")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 14)])

    for section, key in [
        ("Potential warning signs", "red_flags"),
        ("Positive indicators", "positive_indicators"),
        ("Verification findings", "verification"),
        ("Recommended precautions", "recommendations"),
    ]:
        story.append(Paragraph(section, styles["Heading2"]))
        values = scan.details.get(key, [])
        if not values:
            story.append(Paragraph("None identified.", styles["BodyText"]))
        for item in values:
            if isinstance(item, dict):
                content = f"<b>{escape(str(item.get('title', 'Finding')))}</b> — {escape(str(item.get('explanation', '')))}"
            else:
                content = escape(str(item))
            story.append(Paragraph(f"• {content}", styles["BodyText"]))
            story.append(Spacer(1, 4))

    story.extend([Spacer(1, 12), Paragraph(DISCLAIMER, styles["Italic"])])
    SimpleDocTemplate(output, pagesize=letter, rightMargin=46, leftMargin=46).build(story)
    return output.getvalue()
