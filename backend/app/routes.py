import csv
import re
from datetime import datetime, timedelta, timezone
from io import StringIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .detection import analyze_text, get_model_evaluation, verify_url
from .models import Scan, User
from .schemas import AnalysisRequest, URLRequest
from .services import extract_pdf_document, make_report
from .verification import enrich_url_verification

router = APIRouter(prefix="/api")

DEMO_POSTINGS = [
    {
        "days_ago": 92,
        "title": "Software Engineering Intern",
        "company": "Northstar Analytics (Sample)",
        "description": (
            "Work with the Northstar product engineering team on a supervised ten-week "
            "internship. The role includes a published hourly stipend, weekly mentoring, "
            "and a project review. Candidates complete an interview and technical "
            "assessment. There is no application or training fee, and applicants should "
            "apply through the company careers portal."
        ),
        "message": "",
    },
    {
        "days_ago": 48,
        "title": "Remote Data Entry Internship",
        "company": "BrightPath Staffing (Sample)",
        "description": (
            "Remote data entry internship with introductory training and flexible hours. "
            "A refundable registration fee of $35 is required after selection to reserve "
            "your training place. The recruiter says the role starts next week and that "
            "the fee is returned with your first stipend. Request the written policy and "
            "verify the employer independently before paying."
        ),
        "message": "",
    },
    {
        "days_ago": 12,
        "title": "Guaranteed Remote Placement Program",
        "company": "Summit Career Group (Sample)",
        "description": (
            "Guaranteed job placement is offered to every applicant after a short online "
            "session. Pay a registration fee and training fee today to reserve the role. "
            "Send your bank details for stipend processing before the interview. Transfer "
            "the refundable security deposit immediately because enrollment closes soon."
        ),
        "message": "",
    },
]


def persist(db: Session, result: dict, owner_user_id: int, source_text: str = "") -> Scan:
    details = {**result, "source_text": source_text[:30000]}
    scan = Scan(
        company_name=result["company_name"],
        job_title=result["job_title"],
        scan_type=result["scan_type"],
        risk_score=result["risk_score"],
        risk_category=result["risk_category"],
        summary=result["summary"],
        details=details,
        owner_user_id=owner_user_id,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def serialize(scan: Scan) -> dict:
    return {
        "scan_id": scan.id,
        "created_at": scan.created_at.replace(tzinfo=timezone.utc).isoformat(),
        **scan.details,
    }


def get_risk_explanation(scan: Scan) -> list[str]:
    details = scan.details or {}
    red_flags = details.get("red_flags") or []
    if red_flags:
        return [
            f"{flag.get('title', 'Potential warning sign')}: {flag.get('explanation', '')}".rstrip(": ")
            for flag in red_flags
            if isinstance(flag, dict)
        ]

    verification = details.get("verification") or []
    if verification:
        return [
            f"{finding.get('title', 'Verification finding')}: {finding.get('explanation', '')}".rstrip(": ")
            for finding in verification
            if isinstance(finding, dict)
        ]

    positive_indicators = details.get("positive_indicators") or []
    if positive_indicators:
        return positive_indicators

    return [details.get("summary") or scan.summary or "No explanation was saved for this scan."]


@router.post("/analyze")
def analyze(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    text = "\n".join([request.job_title, request.company_name, request.job_description, request.recruitment_message])
    result = analyze_text(
        text, request.company_name, request.job_title,
        application_url=request.application_url, scan_type="job",
    )
    return serialize(persist(db, result, user.id, text))


@router.post("/demo-scans")
def create_demo_scans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (
        db.query(Scan.id)
        .filter(
            Scan.owner_user_id == user.id,
            Scan.details["sample_data"].as_boolean().is_(True),
        )
        .first()
    )
    if existing:
        return {"created": False, "count": 0}
    if db.query(Scan.id).filter(Scan.owner_user_id == user.id).first():
        return {"created": False, "count": 0}

    now = datetime.now(timezone.utc)
    sample_scans = []
    for posting in DEMO_POSTINGS:
        text = "\n".join(
            [posting["title"], posting["company"], posting["description"], posting["message"]]
        )
        result = analyze_text(
            text,
            posting["company"],
            posting["title"],
            scan_type="job",
        )
        result["sample_data"] = True
        result["sample_notice"] = "Illustrative sample only; this is not a real job posting or prior investigation."
        sample_scans.append(
            Scan(
                company_name=posting["company"],
                job_title=posting["title"],
                scan_type="job",
                risk_score=result["risk_score"],
                risk_category=result["risk_category"],
                summary=result["summary"],
                details={**result, "source_text": text},
                owner_user_id=user.id,
                created_at=now - timedelta(days=posting["days_ago"]),
            )
        )
    db.add_all(sample_scans)
    db.commit()
    return {"created": True, "count": len(DEMO_POSTINGS)}


@router.post("/verify")
async def verify(
    request: URLRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    checked = verify_url(request.url, request.company_name, request.contact_email)
    advanced = await enrich_url_verification(request.url, checked)
    risk_score = min(100, checked["risk_score"] + advanced["risk_points"])
    findings = checked["findings"] + advanced["findings"]
    result = {
        "scan_type": "url",
        "company_name": request.company_name,
        "job_title": "",
        "risk_score": risk_score,
        "risk_category": "LOW" if risk_score <= 30 else ("MEDIUM" if risk_score <= 60 else "HIGH"),
        "summary": checked["summary"],
        "red_flags": [],
        "positive_indicators": [],
        "recommendations": [
            "Confirm the exact domain through the employer's independently verified website.",
            "Do not enter passwords, one-time codes, or payment details on an unverified site.",
        ],
        "verification": findings,
        "verification_details": advanced["details"],
        "domain": checked["domain"],
        "url_valid": checked["valid"],
        "https": checked["https"],
        "ml_risk_probability": 0.0,
        "disclaimer": "These DNS, registration, TLS, and optional reputation checks are preliminary signals only. Unavailable data is not a clean verdict, and no check authenticates a company or offer.",
    }
    return serialize(persist(db, result, user.id, request.url))


@router.post("/offer-letter")
async def scan_offer_letter(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")
    contents = await file.read(10 * 1024 * 1024 + 1)
    try:
        text, document_processing = extract_pdf_document(contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    company = ""
    company_match = re.search(r"(?:company|employer)\s*:\s*([^\n]{2,100})", text, re.I)
    if company_match:
        company = company_match.group(1).strip()
    title = ""
    title_match = re.search(r"(?:designation|position|job title|role)\s*:\s*([^\n]{2,100})", text, re.I)
    if title_match:
        title = title_match.group(1).strip()
    salary_match = re.search(
        r"(?:salary|compensation|remuneration|stipend|ctc|pay range)\s*[:\-]?\s*([^\n]{2,100})",
        text,
        re.I,
    )
    if not salary_match:
        salary_match = re.search(
            r"(?:(?:USD|INR)\s*)?(?:\$|₹)\s?[\d,]+(?:\s*(?:to|-)\s*(?:\$|₹)?\s?[\d,]+)?"
            r"(?:\s*(?:per|/)\s*(?:year|month|week|hour|annum))?",
            text,
            re.I,
        )
    result = analyze_text(text, company, title, scan_type="offer_letter")
    result["document_processing"] = document_processing
    result["extracted_details"] = {
        "company": company or "Not identified",
        "job_title": title or "Not identified",
        "salary": salary_match.group(1).strip() if salary_match and salary_match.lastindex else (salary_match.group(0).strip() if salary_match else "Not identified"),
    }
    result["verification"].append({
        "title": "Extracted text review",
        "explanation": (
            f"{'OCR text was recognized from scanned pages' if document_processing['ocr_pages'] else 'Selectable PDF text was extracted'} "
            f"from “{file.filename}”. Extraction does not verify the issuer or authenticity."
        ),
        "severity": "low",
    })
    return serialize(persist(db, result, user.id, text))


@router.get("/scans")
def list_scans(
    search: str = "",
    category: str = "",
    scan_type: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Scan).filter(Scan.owner_user_id == user.id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((Scan.company_name.ilike(term)) | (Scan.job_title.ilike(term)) | (Scan.summary.ilike(term)))
    if category in {"LOW", "MEDIUM", "HIGH"}:
        query = query.filter(Scan.risk_category == category)
    if scan_type in {"job", "offer_letter", "url"}:
        query = query.filter(Scan.scan_type == scan_type)
    return [
        {
            "scan_id": scan.id,
            "created_at": scan.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "company_name": scan.company_name,
            "job_title": scan.job_title,
            "scan_type": scan.scan_type,
            "risk_score": scan.risk_score,
            "risk_category": scan.risk_category,
            "summary": scan.summary,
            "risk_explanation": get_risk_explanation(scan),
            "sample_data": bool(scan.details.get("sample_data", False)),
        }
        for scan in query.order_by(Scan.created_at.desc()).limit(500).all()
    ]


@router.get("/scans.csv")
def export_csv(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Scan ID", "Timestamp UTC", "Company", "Job title", "Type", "Risk score", "Category", "Summary", "Sample data"])
    for scan in db.query(Scan).filter(Scan.owner_user_id == user.id).order_by(Scan.created_at.desc()).all():
        writer.writerow([scan.id, scan.created_at.replace(tzinfo=timezone.utc).isoformat(), scan.company_name, scan.job_title, scan.scan_type, scan.risk_score, scan.risk_category, scan.summary, bool(scan.details.get("sample_data", False))])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=internguard-scans.csv"},
    )


@router.get("/scans/{scan_id}")
def get_scan(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.owner_user_id == user.id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return serialize(scan)


@router.delete("/scans/{scan_id}")
def delete_scan(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.owner_user_id == user.id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    db.delete(scan)
    db.commit()
    return {"deleted": True}


@router.get("/scans/{scan_id}/report.pdf")
def download_report(
    scan_id: int,
    inline: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.owner_user_id == user.id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    disposition = "inline" if inline else "attachment"
    return Response(
        content=make_report(scan),
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="internguard-scan-{scan.id}.pdf"'},
    )


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scans = db.query(Scan).filter(Scan.owner_user_id == user.id).order_by(Scan.created_at.desc()).all()
    sample_count = sum(bool(scan.details.get("sample_data", False)) for scan in scans)
    distribution = {key: sum(1 for scan in scans if scan.risk_category == key) for key in ["LOW", "MEDIUM", "HIGH"]}
    type_counts = {
        key: sum(1 for scan in scans if scan.scan_type == key)
        for key in ["job", "offer_letter", "url"]
    }
    monthly = {}
    for scan in scans:
        month = scan.created_at.strftime("%Y-%m")
        monthly.setdefault(month, {"month": scan.created_at.strftime("%b %Y"), "scans": 0, "high_risk": 0})
        monthly[month]["scans"] += 1
        monthly[month]["high_risk"] += int(scan.risk_category == "HIGH")
    return {
        "total_scans": len(scans),
        "high_risk": distribution["HIGH"],
        "medium_risk": distribution["MEDIUM"],
        "low_risk": distribution["LOW"],
        "distribution": [{"name": key.title(), "value": distribution[key]} for key in ["LOW", "MEDIUM", "HIGH"]],
        "scan_type_summary": [
            {"name": "Job & internship", "value": type_counts["job"]},
            {"name": "Offer letters", "value": type_counts["offer_letter"]},
            {"name": "URL verification", "value": type_counts["url"]},
        ],
        "monthly_trends": [monthly[key] for key in sorted(monthly)][-6:],
        "recent_scans": [
            {
                "scan_id": scan.id, "created_at": scan.created_at.replace(tzinfo=timezone.utc).isoformat(),
                "company_name": scan.company_name, "job_title": scan.job_title,
                "scan_type": scan.scan_type, "risk_score": scan.risk_score, "risk_category": scan.risk_category,
                "sample_data": bool(scan.details.get("sample_data", False)),
            } for scan in scans[:6]
        ],
        "sample_data": sample_count > 0,
        "sample_scan_count": sample_count,
    }


@router.get("/model/metrics")
def model_metrics(user: User = Depends(get_current_user)):
    return get_model_evaluation()
