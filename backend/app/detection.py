import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split

DISCLAIMER = (
    "InternGuard provides preliminary risk indicators, not definitive proof "
    "of fraud or authenticity. Verify important claims independently."
)

TRAINING_DATA = Path(__file__).resolve().parents[1] / "data" / "demo_training.csv"
PUBLIC_TRAINING_DATA = Path(__file__).resolve().parents[1] / "data" / "real_job_postings_cc0.csv.gz"
DATASET_PAGE = "https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction"

RULES = [
    (
        "Upfront payment request",
        30,
        re.compile(
            r"\b(registration|application|processing|onboarding)\s+fee\b"
            r"|\bpay\s+(?:a|the|an)?\s*(?:fee|deposit)\b"
            r"|\bfee\s+(?:is\s+)?required\b",
            re.I,
        ),
        "The message appears to request an upfront recruitment or application payment.",
    ),
    (
        "Security deposit",
        28,
        re.compile(r"\bsecurity\s+deposit\b|\brefundable\s+deposit\b", re.I),
        "A deposit is requested in connection with the opportunity.",
    ),
    (
        "Paid training requirement",
        22,
        re.compile(r"\b(?:training|orientation)\s+fee\b|\bpay\s+for\s+training\b", re.I),
        "The applicant may be required to pay for training or orientation.",
    ),
    (
        "Urgent payment pressure",
        12,
        re.compile(r"\b(pay|transfer|send)\b.{0,45}\b(today|immediately|within\s+24\s+hours)\b", re.I),
        "Time pressure is paired with a payment request.",
    ),
    (
        "Unrealistic compensation",
        20,
        re.compile(
            r"\b(?:earn|salary|income)\b.{0,50}\b(?:\$\s?\d{4,}|₹\s?[\d,]{5,}|\d{4,}\s*(?:per\s+)?(?:day|week))\b"
            r"|\b(?:guaranteed|minimum)\s+(?:income|salary)\s+of\s+(?:\$\s?\d{4,}|₹\s?[\d,]{5,})",
            re.I,
        ),
        "The compensation claim may be unusually high or guaranteed without enough context.",
    ),
    (
        "Guaranteed placement claim",
        18,
        re.compile(r"\bguaranteed\s+(?:job|placement|offer|employment)\b", re.I),
        "A guaranteed job or placement is promised before a normal selection process.",
    ),
    (
        "Sensitive information request",
        18,
        re.compile(
            r"\b(?:send|share|submit|provide)\b.{0,60}\b(?:password|otp|one.time.password|bank details|card number|passport|social security|national id|aadhaar|tax id|ssn|identity document)\b",
            re.I,
        ),
        "The message asks for highly sensitive credentials or financial information.",
    ),
    (
        "Unusual employment condition",
        12,
        re.compile(r"\b(?:unpaid trial|pay for (?:company )?equipment|equipment fee|pay to return|employment bond.{0,30}fee)\b", re.I),
        "The opportunity describes an unusual trial, equipment payment, or employment-bond fee; request written terms and verify before agreeing.",
    ),
    (
        "Suspicious contact email",
        16,
        re.compile(r"\b[\w.+-]+@(?:gmail|yahoo|outlook|hotmail|protonmail)\.[a-z]{2,}\b", re.I),
        "Recruitment contact uses a general-purpose email provider rather than a company domain.",
    ),
    (
        "Unusually urgent recruitment",
        10,
        re.compile(r"\b(?:act now|limited slots|respond urgently|offer expires today|immediate hiring)\b", re.I),
        "High-pressure language is used to rush the decision.",
    ),
]

MODEL: Pipeline
MODEL_EVALUATION: dict


def load_model() -> Pipeline:
    global MODEL_EVALUATION
    if PUBLIC_TRAINING_DATA.exists():
        data = pd.read_csv(PUBLIC_TRAINING_DATA)
        source = "Kaggle Real / Fake Job Posting Prediction (EMSCAD)"
        license_name = "CC0 1.0 Universal"
        source_url = DATASET_PAGE
        is_baseline = False
    else:
        data = pd.read_csv(TRAINING_DATA)
        source = "Synthetic demonstration baseline"
        license_name = "Project-generated demonstration data"
        source_url = None
        is_baseline = True

    texts = data["text"].fillna("").astype(str).str.slice(0, 6000)
    labels = data["label"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=3,
                    max_features=30000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    solver="liblinear",
                    dual=True,
                    tol=1e-3,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    MODEL_EVALUATION = {
        "source": source,
        "license": license_name,
        "source_url": source_url,
        "baseline": is_baseline,
        "positive_label": "fraudulent",
        "records": int(len(data)),
        "train_records": int(len(x_train)),
        "test_records": int(len(x_test)),
        "split": "80/20 stratified holdout",
        "random_state": 42,
        "class_counts": {
            "legitimate": int((labels == 0).sum()),
            "fraudulent": int((labels == 1).sum()),
        },
        "metrics": {
            "precision": float(precision_score(y_test, predictions, pos_label=1, zero_division=0)),
            "recall": float(recall_score(y_test, predictions, pos_label=1, zero_division=0)),
            "f1": float(f1_score(y_test, predictions, pos_label=1, zero_division=0)),
        },
        "confusion_matrix": {
            "labels": ["legitimate", "fraudulent"],
            "rows": matrix.tolist(),
        },
        "evaluation_note": (
            "Metrics are from a single stratified holdout of this dataset, not an external validation set. "
            "Historical dataset content and class balance may not reflect current scams."
        ),
    }
    return pipeline


MODEL = load_model()


def get_model_evaluation() -> dict:
    return MODEL_EVALUATION.copy()


def classify(score: int) -> str:
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    return "HIGH"


def _remove_clear_negations(text: str) -> str:
    return re.sub(
        r"\b(?:no|never|does not require|do not pay|don't pay)\b[^.!?\n]{0,80}",
        " ",
        text,
        flags=re.I,
    )


def analyze_text(
    text: str,
    company_name: str = "",
    job_title: str = "",
    contact_email: str = "",
    application_url: str = "",
    scan_type: str = "job",
) -> dict:
    normalized_text = " ".join(text.split())
    searchable_text = _remove_clear_negations(normalized_text)
    findings = []
    rule_score = 0
    for title, weight, pattern, explanation in RULES:
        if pattern.search(searchable_text):
            findings.append(
                {"title": title, "explanation": explanation, "severity": "high" if weight >= 18 else "medium"}
            )
            rule_score += weight

    if not company_name.strip():
        findings.append(
            {
                "title": "Company identity not provided",
                "explanation": "No company name was supplied, so the employer cannot be cross-checked from this submission.",
                "severity": "medium",
            }
        )
        rule_score += 10
    if len(normalized_text) < 120:
        findings.append(
            {
                "title": "Limited opportunity details",
                "explanation": "The submitted text is brief, limiting the checks that can be performed.",
                "severity": "low",
            }
        )
        rule_score += 6

    model_probability = float(MODEL.predict_proba([normalized_text])[0][1])
    score = round(min(100, max(0, 0.75 * min(rule_score, 100) + 0.25 * model_probability * 100)))
    category = classify(score)
    positive_indicators = []
    if company_name.strip():
        positive_indicators.append("A company name was provided for independent verification.")
    if re.search(r"\b(interview|selection process|technical assessment)\b", normalized_text, re.I):
        positive_indicators.append("The text mentions a conventional interview or assessment step.")
    if re.search(r"\b(no fees|never pay|does not require (?:a )?fee)\b", normalized_text, re.I):
        positive_indicators.append("The text explicitly states that no recruitment fee is required.")
    if not findings:
        positive_indicators.append("No configured high-signal warning phrases were detected in the submitted text.")

    recommendations = [
        "Contact the employer using contact details obtained from its independently verified official website.",
        "Do not pay application, training, equipment, or security fees to secure a role.",
        "Never share passwords, one-time codes, or banking credentials during recruitment.",
    ]
    verification = []
    if application_url:
        verification = verify_url(application_url, company_name, contact_email)["findings"]

    summary = (
        f"{len(findings)} potential warning sign(s) were identified."
        if findings
        else "No configured high-signal warning phrases were identified; this is not proof of legitimacy."
    )
    return {
        "scan_type": scan_type,
        "company_name": company_name.strip(),
        "job_title": job_title.strip(),
        "risk_score": score,
        "risk_category": category,
        "summary": summary,
        "red_flags": findings,
        "positive_indicators": positive_indicators,
        "recommendations": recommendations,
        "verification": verification,
        "ml_risk_probability": round(model_probability, 4),
        "disclaimer": DISCLAIMER,
    }


SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly", "buff.ly"}
FREE_HOSTS = {"sites.google.com", "weebly.com", "wixsite.com", "wordpress.com"}


def verify_url(url: str, company_name: str = "", contact_email: str = "") -> dict:
    value = url.strip()
    candidate = value if "://" in value else f"https://{value}"
    try:
        parsed = urlparse(candidate)
        hostname = (parsed.hostname or "").rstrip(".").lower()
        if hostname:
            hostname = hostname.encode("idna").decode("ascii")
        port = parsed.port
        try:
            ip_address = ipaddress.ip_address(hostname) if hostname else None
        except ValueError:
            ip_address = None
        domain_valid = (
            bool(hostname)
            and "." in hostname
            and not hostname.endswith((".local", ".localhost"))
        )
        valid = (
            parsed.scheme in {"http", "https"}
            and (domain_valid or ip_address is not None)
            and parsed.username is None
            and parsed.password is None
            and (port is None or 1 <= port <= 65535)
        )
    except (ValueError, UnicodeError):
        hostname, valid = "", False
        ip_address, port = None, None

    findings = []
    score = 0
    if not valid:
        findings.append({"title": "Invalid URL format", "explanation": "The input is not a valid web URL with a recognizable hostname.", "severity": "high"})
        score += 45
    else:
        if parsed.username is not None or parsed.password is not None:
            findings.append({"title": "URL contains embedded credentials", "explanation": "User information embedded in the URL is not accepted for verification.", "severity": "high"})
            score += 30
        if parsed.scheme != "https":
            findings.append({"title": "Connection is not HTTPS", "explanation": "The URL uses HTTP, so traffic to the site may not be encrypted.", "severity": "medium"})
            score += 15
        if hostname in SHORTENERS:
            findings.append({"title": "Shortened URL", "explanation": "The URL shortener hides the final destination; inspect it through a trusted channel before opening.", "severity": "medium"})
            score += 20
        if hostname in FREE_HOSTS or any(hostname.endswith("." + suffix) for suffix in FREE_HOSTS):
            findings.append({"title": "Hosted on a general-purpose site builder", "explanation": "A free hosting domain is not evidence of fraud, but it does not establish an employer's identity.", "severity": "low"})
            score += 12
        if len(hostname.split(".")) > 4 or re.search(r"\d{4,}|-{2,}", hostname):
            findings.append({"title": "Unusual domain pattern", "explanation": "The hostname has structural patterns sometimes used in misleading domains; confirm the exact spelling independently.", "severity": "medium"})
            score += 12
        if ip_address is not None:
            findings.append({"title": "URL uses a literal IP address", "explanation": "A literal IP address does not establish an employer's domain identity; domain DNS, registration, and reputation checks are skipped.", "severity": "medium"})
            score += 15
        if port not in (None, 80, 443):
            findings.append({"title": "Non-standard web port", "explanation": "The URL uses a non-standard port. Automated connection checks are restricted to standard HTTPS port 443.", "severity": "low"})
            score += 8

    email_domain = contact_email.rsplit("@", 1)[-1].lower().strip() if "@" in contact_email else ""
    if email_domain and hostname and email_domain != hostname and not hostname.endswith("." + email_domain) and not email_domain.endswith("." + hostname):
        findings.append({"title": "Email and website domains differ", "explanation": "The supplied contact email domain does not match the website domain. Legitimate organizations can use separate domains, so verify independently.", "severity": "medium"})
        score += 15
    if not findings and valid:
        findings.append({"title": "No structural warning detected", "explanation": "The URL passed basic format and domain-pattern checks only. The site and employer have not been independently authenticated.", "severity": "low"})
    if company_name:
        findings.append({"title": "Company identity not authenticated", "explanation": f"The name “{company_name}” cannot be verified from URL structure alone.", "severity": "medium"})
    return {
        "valid": valid,
        "domain": hostname or None,
        "https": bool(valid and parsed.scheme == "https"),
        "findings": findings,
        "risk_score": min(100, score),
        "risk_category": classify(min(100, score)),
        "summary": "Basic URL checks completed; they do not establish that a company or website is genuine.",
    }
