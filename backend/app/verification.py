import asyncio
import ipaddress
import json
import os
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import dns.asyncresolver
import dns.exception
import dns.resolver
import httpx
import tldextract

BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
_BOOTSTRAP_TTL_SECONDS = 24 * 60 * 60
_bootstrap_loaded_at = 0.0
_rdap_services: dict[str, str] = {}
_bootstrap_lock = asyncio.Lock()
_domain_extractor = tldextract.TLDExtract(suffix_list_urls=())


async def _read_limited(response: httpx.Response, limit: int) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > limit:
            raise ValueError("Remote response exceeded the size limit.")
        body.extend(chunk)
    return bytes(body)


async def _dns_query(
    resolver: dns.asyncresolver.Resolver, domain: str, record_type: str
) -> tuple[str, list[str]]:
    try:
        answer = await resolver.resolve(domain, record_type, lifetime=1.6)
        values = [record.to_text().rstrip(".") for record in answer[:8]]
        return "found", values
    except dns.resolver.NXDOMAIN:
        return "not_found", []
    except dns.resolver.NoAnswer:
        return "no_record", []
    except (dns.resolver.NoNameservers, dns.exception.Timeout, OSError):
        return "unavailable", []


async def lookup_dns(domain: str) -> dict:
    resolver = dns.asyncresolver.Resolver(configure=True)
    resolver.timeout = 1.0
    queries = await asyncio.gather(
        *(_dns_query(resolver, domain, kind) for kind in ("A", "AAAA", "MX", "NS"))
    )
    records = {kind: values for kind, (_, values) in zip(("A", "AAAA", "MX", "NS"), queries)}
    states = [state for state, _ in queries]
    addresses = records["A"] + records["AAAA"]
    if addresses:
        status = "verified"
        message = "DNS address records were returned by the configured resolver."
    elif all(state == "not_found" for state in states):
        status = "not_found"
        message = "The configured DNS resolver reports that this name does not exist."
    elif all(state in {"no_record", "not_found"} for state in states):
        status = "no_records"
        message = "No A, AAAA, MX, or NS records were returned."
    elif any(state == "found" for state in states):
        status = "partial"
        message = "Some DNS records were returned; other record types may be missing or unavailable."
    else:
        status = "unavailable"
        message = "DNS lookup timed out or the configured resolver was unavailable."

    non_public = []
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if not address.is_global:
            non_public.append(value)
    return {
        "status": status,
        "records": records,
        "non_public_addresses": non_public,
        "message": message,
    }


async def check_https_certificate(
    domain: str, scheme: str, port: int | None, dns_result: dict
) -> dict:
    if scheme != "https":
        return {
            "status": "not_applicable",
            "valid": False,
            "message": "The submitted URL uses HTTP; no TLS certificate check was made.",
        }
    if port not in (None, 443):
        return {
            "status": "not_checked",
            "valid": False,
            "message": "TLS checks are restricted to the standard HTTPS port (443).",
        }

    candidates = []
    for value in dns_result.get("records", {}).get("A", []) + dns_result.get("records", {}).get("AAAA", []):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.is_global:
            candidates.append((value, socket.AF_INET6 if address.version == 6 else socket.AF_INET))
    if not candidates:
        return {
            "status": "unavailable",
            "valid": False,
            "message": "No publicly routable DNS address was available for a safe TLS check.",
        }

    context = ssl.create_default_context()
    for address, family in candidates[:2]:
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    host=address,
                    port=443,
                    family=family,
                    ssl=context,
                    server_hostname=domain,
                ),
                timeout=2.5,
            )
            writer.close()
            await writer.wait_closed()
            return {
                "status": "verified",
                "valid": True,
                "message": "A TLS certificate chain for this hostname validated successfully.",
            }
        except ssl.SSLCertVerificationError:
            return {
                "status": "invalid",
                "valid": False,
                "message": "The TLS certificate could not be validated for this hostname.",
            }
        except (ssl.SSLError, asyncio.TimeoutError, OSError):
            if writer is not None:
                writer.close()

    return {
        "status": "unavailable",
        "valid": False,
        "message": "TLS could not be checked because the host did not complete a connection before the timeout.",
    }


async def _load_rdap_services(client: httpx.AsyncClient) -> dict[str, str]:
    global _bootstrap_loaded_at, _rdap_services
    if _rdap_services and time.monotonic() - _bootstrap_loaded_at < _BOOTSTRAP_TTL_SECONDS:
        return _rdap_services

    async with _bootstrap_lock:
        if _rdap_services and time.monotonic() - _bootstrap_loaded_at < _BOOTSTRAP_TTL_SECONDS:
            return _rdap_services
        async with client.stream("GET", BOOTSTRAP_URL) as response:
            response.raise_for_status()
            payload = json.loads(await _read_limited(response, 2 * 1024 * 1024))

        services = {}
        for suffixes, urls in payload.get("services", []):
            secure_urls = [
                url.rstrip("/")
                for url in urls
                if urlparse(url).scheme == "https"
                and urlparse(url).hostname
                and not urlparse(url).username
                and urlparse(url).port in (None, 443)
            ]
            if not secure_urls:
                continue
            for suffix in suffixes:
                services[suffix.lower()] = secure_urls[0]
        _rdap_services = services
        _bootstrap_loaded_at = time.monotonic()
        return services


def _registrable_domain(hostname: str) -> str:
    extracted = _domain_extractor(hostname)
    return extracted.top_domain_under_public_suffix or hostname


def _registration_fields(payload: dict, domain: str) -> dict:
    registration_date = None
    expiration_date = None
    for event in payload.get("events", []):
        action = event.get("eventAction", "").lower()
        if action in {"registration", "registered"}:
            registration_date = event.get("eventDate")
        elif action in {"expiration", "expiry"}:
            expiration_date = event.get("eventDate")

    registrar = None
    for entity in payload.get("entities", []):
        if "registrar" not in entity.get("roles", []):
            continue
        cards = entity.get("vcardArray", [])
        if len(cards) > 1:
            for item in cards[1]:
                if len(item) > 3 and item[0] == "fn":
                    registrar = str(item[3])
                    break
        if registrar:
            break

    age_days = None
    if registration_date:
        try:
            registered = datetime.fromisoformat(registration_date.replace("Z", "+00:00"))
            age_days = max(0, (datetime.now(timezone.utc) - registered).days)
        except ValueError:
            registration_date = None

    return {
        "status": "verified",
        "domain": domain,
        "registration_date": registration_date,
        "age_days": age_days,
        "expiration_date": expiration_date,
        "registrar": registrar,
        "message": "Registration data was retrieved from the authoritative RDAP service selected by the IANA bootstrap.",
    }


async def lookup_registration(domain: str, client: httpx.AsyncClient) -> dict:
    registrable = _registrable_domain(domain)
    suffix = registrable.rsplit(".", 1)[-1].lower()
    try:
        services = await _load_rdap_services(client)
        base_url = services.get(suffix)
        if not base_url:
            return {
                "status": "unavailable",
                "domain": registrable,
                "message": f"No HTTPS RDAP service is listed by IANA for .{suffix}.",
            }
        url = f"{base_url}/domain/{quote(registrable, safe='.-')}"
        async with client.stream("GET", url, headers={"Accept": "application/rdap+json, application/json"}) as response:
            if response.status_code == 404:
                return {
                    "status": "not_found",
                    "domain": registrable,
                    "message": "The RDAP registry did not return a registration record for this domain.",
                }
            if response.status_code == 429:
                return {
                    "status": "unavailable",
                    "domain": registrable,
                    "message": "The RDAP registry rate-limited this lookup.",
                }
            if response.is_redirect:
                return {
                    "status": "unavailable",
                    "domain": registrable,
                    "message": "The RDAP registry redirected the request; redirects are disabled for safety.",
                }
            response.raise_for_status()
            payload = json.loads(await _read_limited(response, 512 * 1024))
        return _registration_fields(payload, registrable)
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, OSError):
        return {
            "status": "unavailable",
            "domain": registrable,
            "message": "RDAP registration information could not be retrieved within the safe request limits.",
        }


async def check_virustotal(domain: str, api_key: str | None = None) -> dict:
    key = api_key or os.getenv("VIRUSTOTAL_API_KEY", "").strip()
    if not key:
        return {
            "provider": "VirusTotal",
            "status": "not_configured",
            "message": "Not queried. Configure VIRUSTOTAL_API_KEY to enable this optional reputation check.",
        }

    url = f"https://www.virustotal.com/api/v3/domains/{quote(domain, safe='.-')}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0), follow_redirects=False) as client:
            async with client.stream("GET", url, headers={"x-apikey": key}) as response:
                if response.status_code in {401, 403}:
                    return {
                        "provider": "VirusTotal",
                        "status": "unavailable",
                        "message": "VirusTotal rejected the configured API key.",
                    }
                if response.status_code == 429:
                    return {
                        "provider": "VirusTotal",
                        "status": "unavailable",
                        "message": "VirusTotal rate-limited this check.",
                    }
                if response.status_code == 404:
                    return {
                        "provider": "VirusTotal",
                        "status": "unavailable",
                        "message": "VirusTotal has no domain record; this is not a clean verdict.",
                    }
                response.raise_for_status()
                payload = json.loads(await _read_limited(response, 256 * 1024))
        stats = payload.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        malicious = int(stats.get("malicious", 0))
        suspicious = int(stats.get("suspicious", 0))
        return {
            "provider": "VirusTotal",
            "status": "checked",
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": int(stats.get("harmless", 0)),
            "reputation": payload.get("data", {}).get("attributes", {}).get("reputation"),
            "message": (
                "No malicious or suspicious votes were returned. Absence of detections is not proof of safety."
                if malicious == 0 and suspicious == 0
                else f"VirusTotal reports {malicious} malicious and {suspicious} suspicious engine result(s)."
            ),
        }
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, TypeError):
        return {
            "provider": "VirusTotal",
            "status": "unavailable",
            "message": "VirusTotal could not be reached within the safe request limits.",
        }


async def enrich_url_verification(url: str, structural: dict) -> dict:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = structural.get("domain")
    if not structural.get("valid") or not domain:
        unavailable = {
            "status": "unavailable",
            "message": "The URL has no valid public hostname to check.",
        }
        return {
            "details": {
                "dns": unavailable,
                "registration": unavailable,
                "https": {"status": "not_checked", "valid": False, "message": unavailable["message"]},
                "threat_intelligence": {
                    "provider": "VirusTotal",
                    "status": "not_checked",
                    "message": unavailable["message"],
                },
            },
            "risk_points": 0,
            "findings": [],
        }

    try:
        address = ipaddress.ip_address(domain)
    except ValueError:
        address = None
    if address is not None:
        no_dns = {"status": "not_applicable", "records": {}, "message": "A literal IP address was supplied; DNS and domain registration checks do not apply."}
        return {
            "details": {
                "dns": no_dns,
                "registration": {"status": "not_applicable", "domain": domain, "message": "IP addresses have no domain registration record."},
                "https": {"status": "not_checked", "valid": False, "message": "TLS check skipped for literal IP addresses."},
                "threat_intelligence": {"provider": "VirusTotal", "status": "not_checked", "message": "Domain-only reputation lookup was skipped."},
            },
            "risk_points": 0,
            "findings": [],
        }

    try:
        domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        unavailable = {"status": "unavailable", "message": "The hostname could not be normalized for safe lookups."}
        return {
            "details": {
                "dns": unavailable,
                "registration": unavailable,
                "https": {"status": "not_checked", "valid": False, "message": unavailable["message"]},
                "threat_intelligence": {"provider": "VirusTotal", "status": "not_checked", "message": unavailable["message"]},
            },
            "risk_points": 0,
            "findings": [],
        }

    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0), follow_redirects=False) as client:
        dns_result = await lookup_dns(domain)
        tls_task = check_https_certificate(domain, parsed.scheme, parsed.port, dns_result)
        registration_task = lookup_registration(domain, client)
        threat_task = check_virustotal(domain)
        tls_result, registration_result, threat_result = await asyncio.gather(
            tls_task, registration_task, threat_task
        )

    findings = []
    risk_points = 0
    age_days = registration_result.get("age_days")
    if registration_result.get("status") == "verified" and age_days is not None and age_days < 30:
        findings.append({
            "title": "Recently registered domain",
            "explanation": f"RDAP reports this domain was registered {age_days} day(s) ago. New domains can be legitimate; verify the employer independently.",
            "severity": "medium",
        })
        risk_points += 15
    if tls_result.get("status") == "invalid":
        findings.append({
            "title": "TLS certificate validation failed",
            "explanation": tls_result["message"],
            "severity": "medium",
        })
        risk_points += 12
    malicious = threat_result.get("malicious", 0)
    suspicious = threat_result.get("suspicious", 0)
    if malicious:
        findings.append({
            "title": "Threat-intelligence detections reported",
            "explanation": threat_result["message"],
            "severity": "high",
        })
        risk_points += min(45, malicious * 10)
    elif suspicious:
        findings.append({
            "title": "Threat-intelligence caution reported",
            "explanation": threat_result["message"],
            "severity": "medium",
        })
        risk_points += 12

    return {
        "details": {
            "dns": dns_result,
            "registration": registration_result,
            "https": tls_result,
            "threat_intelligence": threat_result,
        },
        "risk_points": risk_points,
        "findings": findings,
    }
