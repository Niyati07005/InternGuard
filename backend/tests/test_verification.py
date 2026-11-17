import asyncio

import pytest

from app import verification
from app.detection import verify_url


def test_registrable_domain_respects_multi_label_public_suffix():
    assert verification._registrable_domain("jobs.example.co.uk") == "example.co.uk"
    assert verification._registrable_domain("careers.example.com") == "example.com"


def test_url_enrichment_keeps_unavailable_checks_distinct(monkeypatch):
    async def dns_lookup(domain):
        return {
            "status": "verified",
            "records": {"A": ["203.0.113.8"], "AAAA": [], "MX": [], "NS": []},
            "message": "Test DNS result.",
        }

    async def tls_check(domain, scheme, port, dns_result):
        return {"status": "verified", "valid": True, "message": "Test TLS result."}

    async def registration_lookup(domain, client):
        return {"status": "unavailable", "domain": domain, "message": "RDAP timed out."}

    async def threat_lookup(domain):
        return {"provider": "VirusTotal", "status": "not_configured", "message": "No API key."}

    monkeypatch.setattr(verification, "lookup_dns", dns_lookup)
    monkeypatch.setattr(verification, "check_https_certificate", tls_check)
    monkeypatch.setattr(verification, "lookup_registration", registration_lookup)
    monkeypatch.setattr(verification, "check_virustotal", threat_lookup)

    structural = verify_url("https://jobs.example.co.uk")
    result = asyncio.run(
        verification.enrich_url_verification("https://jobs.example.co.uk", structural)
    )

    assert result["details"]["dns"]["status"] == "verified"
    assert result["details"]["https"]["status"] == "verified"
    assert result["details"]["registration"]["status"] == "unavailable"
    assert result["details"]["threat_intelligence"]["status"] == "not_configured"
    assert result["risk_points"] == 0
    assert not result["findings"]
