import pytest
import pymupdf

from app.detection import MODEL_EVALUATION, analyze_text, verify_url
from app.services import extract_pdf_document, extract_pdf_text


def test_payment_and_guarantee_raise_risk():
    result = analyze_text(
        "Pay a registration fee today to secure your guaranteed job placement. "
        "Send your bank details for a salary of 10000 dollars every day.",
        "QuickHire",
        "Remote intern",
    )
    assert result["risk_score"] > 30
    assert result["risk_category"] in {"MEDIUM", "HIGH"}
    assert len(result["red_flags"]) >= 3


def test_conventional_posting_has_no_high_signal_flags():
    result = analyze_text(
        "We are hiring a software engineering intern for a ten week paid project. "
        "Candidates apply through our careers page and complete an interview and technical assessment. "
        "The published salary range is hourly and no application fee is required.",
        "Example Labs",
        "Software engineering intern",
    )
    assert result["risk_score"] <= 30
    assert result["risk_category"] == "LOW"


def test_url_checker_does_not_authenticate_site():
    result = verify_url("http://bit.ly/offer", "Example Co", "recruiter@example.org")
    titles = {item["title"] for item in result["findings"]}
    assert result["valid"] is True
    assert {"Connection is not HTTPS", "Shortened URL", "Email and website domains differ"} <= titles


def test_sensitive_identity_documents_are_flagged():
    result = analyze_text(
        "Please submit your passport and national ID before the interview.",
        "Northstar Labs",
        "Operations Intern",
    )
    assert "Sensitive information request" in {item["title"] for item in result["red_flags"]}


def test_image_only_pdf_is_reported_as_unreadable():
    document = pymupdf.open()
    document.new_page()
    contents = document.tobytes()
    document.close()
    with pytest.raises(ValueError, match="Scanned/image-only"):
        extract_pdf_text(contents)


def test_real_dataset_holdout_metrics_are_measured():
    assert MODEL_EVALUATION["baseline"] is False
    assert MODEL_EVALUATION["license"] == "CC0 1.0 Universal"
    assert MODEL_EVALUATION["split"] == "80/20 stratified holdout"
    assert MODEL_EVALUATION["records"] == 17880
    assert sum(map(sum, MODEL_EVALUATION["confusion_matrix"]["rows"])) == MODEL_EVALUATION["test_records"]
    assert all(0 <= value <= 1 for value in MODEL_EVALUATION["metrics"].values())


def test_scanned_pdf_uses_ocr():
    source = pymupdf.open()
    source_page = source.new_page(width=612, height=792)
    source_page.insert_text((60, 110), "Company: Northstar Labs", fontsize=24)
    source_page.insert_text((60, 160), "Position: Software Intern", fontsize=24)
    png = source_page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
    source.close()

    scanned = pymupdf.open()
    scanned_page = scanned.new_page(width=612, height=792)
    scanned_page.insert_image(scanned_page.rect, stream=png)
    contents = scanned.tobytes()
    scanned.close()

    text, processing = extract_pdf_document(contents)
    assert processing["mode"] == "ocr"
    assert processing["ocr_pages"] == 1
    assert "Northstar" in text
