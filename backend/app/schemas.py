import re

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,63}", value.strip()):
            raise ValueError("Enter a valid email address.")
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str


class AnalysisRequest(BaseModel):
    job_title: str = Field(min_length=2, max_length=200)
    company_name: str = Field(default="", max_length=200)
    job_description: str = Field(min_length=20, max_length=30000)
    recruitment_message: str = Field(default="", max_length=10000)
    application_url: str = Field(default="", max_length=2000)


class URLRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2000)
    company_name: str = Field(default="", max_length=200)
    contact_email: str = Field(default="", max_length=320)


class Finding(BaseModel):
    title: str
    explanation: str
    severity: str


class AnalysisResult(BaseModel):
    scan_id: int
    created_at: str
    scan_type: str
    company_name: str
    job_title: str
    risk_score: int
    risk_category: str
    summary: str
    red_flags: list[Finding]
    positive_indicators: list[str]
    recommendations: list[str]
    verification: list[str]
    ml_risk_probability: float
    disclaimer: str
