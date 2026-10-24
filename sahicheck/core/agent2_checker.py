"""Agent 2: Deterministic rule checker evaluating job offer extractions and text."""

import json
import re
import sys
from pathlib import Path
from typing import Any

import rapidfuzz.fuzz as fuzz
import tldextract

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from schemas import ExtractionResult, Flag

# Bundled suffix list only (no network downloads)
_TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())

# Load data files once at import time
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

with open(DATA_DIR / "rules.json", "r", encoding="utf-8") as f:
    RULES_DATA: dict[str, Any] = json.load(f)

with open(DATA_DIR / "blocklist.json", "r", encoding="utf-8") as f:
    BLOCKLIST_DATA: dict[str, Any] = json.load(f)

with open(DATA_DIR / "real_companies.json", "r", encoding="utf-8") as f:
    REAL_COMPANIES: list[dict[str, Any]] = json.load(f)

FREE_MAIL_DOMAINS: set[str] = set(RULES_DATA.get("free_mail_domains", []))
SUSPICIOUS_TLDS: set[str] = set(RULES_DATA.get("suspicious_tlds", []))
SHORTENERS: set[str] = set(RULES_DATA.get("shorteners", []))
LOOKALIKE_THRESHOLD: int = int(RULES_DATA.get("lookalike_threshold", 85))
BLOCKLIST_DOMAINS: set[str] = set(BLOCKLIST_DATA.get("domains", []))

# Pre-compile keyword rule regexes
KEYWORD_RULES = []
for r in RULES_DATA.get("keyword_rules", []):
    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in r.get("patterns", [])]
    KEYWORD_RULES.append({
        "id": r["id"],
        "severity": r["severity"],
        "why": r["why"],
        "patterns": compiled_patterns,
    })


def claimed_company(extraction: ExtractionResult, text: str) -> dict[str, Any] | None:
    """Return matching real_companies.json entry or None.
    
    Checks extracted company name first, then scans the text for known aliases.
    """
    comp_extracted = (extraction.extracted.company or "").strip().lower()
    if comp_extracted:
        for entry in REAL_COMPANIES:
            if entry["name"].lower() == comp_extracted:
                return entry
            for alias in entry.get("aliases", []):
                al = alias.lower()
                if al == comp_extracted or al in comp_extracted:
                    return entry

    if text:
        text_lower = text.lower()
        for entry in REAL_COMPANIES:
            name = entry["name"].lower()
            if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
                return entry
            for alias in entry.get("aliases", []):
                al = alias.lower()
                if re.search(r'\b' + re.escape(al) + r'\b', text_lower):
                    return entry

    return None


def _downgrade_severity(sev: str) -> str:
    """Downgrade severity one level when based on unverified OCR/image fields."""
    if sev == "high":
        return "medium"
    if sev == "medium":
        return "low"
    return "low"


def _get_registered_domain(ext: Any, fallback: str = "") -> str:
    """Extract registered domain (domain.suffix) cleanly across tldextract versions."""
    res = getattr(ext, "top_domain_under_public_suffix", None) or getattr(ext, "registered_domain", None)
    return (res or fallback).lower()


def run_checker(extraction: ExtractionResult, text: str) -> list[Flag]:
    """Execute deterministic rule checks against extraction and raw text."""
    flags: list[Flag] = []
    seen_ids: set[str] = set()

    unverified = set(extraction.extracted.unverified_fields or [])
    company_entry = claimed_company(extraction, text)
    official_domains = [d.lower() for d in company_entry.get("domains", [])] if company_entry else []

    # -------------------------------------------------------------------------
    # a) Domain Analysis for Emails and URLs
    # -------------------------------------------------------------------------
    # Gather domain entities from extraction
    email_entities = list(extraction.extracted.emails)
    url_entities = list(extraction.extracted.urls)

    # 1. free_mail_hr check
    for email in email_entities:
        if "@" not in email:
            continue
        domain_part = email.rsplit("@", 1)[-1].strip().lower()
        ext = _TLD_EXTRACTOR(domain_part)
        reg_domain = _get_registered_domain(ext, domain_part)

        if reg_domain in FREE_MAIL_DOMAINS or domain_part in FREE_MAIL_DOMAINS:
            rule_id = "free_mail_hr"
            if rule_id not in seen_ids:
                # Severity is high if claiming to be a real company, else medium
                sev = "high" if company_entry is not None else "medium"
                if "company" in unverified and sev == "high":
                    sev = _downgrade_severity(sev)
                if "emails" in unverified:
                    sev = _downgrade_severity(sev)

                flags.append(Flag(
                    id=rule_id,
                    severity=sev,
                    evidence=email,
                    why_it_matters="Official company recruiters use corporate domain emails, not free personal email accounts (like Gmail or Yahoo).",
                ))
                seen_ids.add(rule_id)
            break

    # 2. lookalike_domain, suspicious_tld, url_shortener, blocklisted_domain
    all_domains_to_check: list[tuple[str, str, str]] = []  # (source_token, reg_domain, fqdn_or_raw)

    for email in email_entities:
        if "@" in email:
            d = email.rsplit("@", 1)[-1].strip().lower()
            ext = _TLD_EXTRACTOR(d)
            reg = _get_registered_domain(ext, d)
            all_domains_to_check.append((email, reg, ext.fqdn.lower() or d))

    for url in url_entities:
        ext = _TLD_EXTRACTOR(url)
        reg = _get_registered_domain(ext)
        fqdn = ext.fqdn.lower()
        if reg or fqdn:
            all_domains_to_check.append((url, reg or fqdn, fqdn or reg))

    for source_token, reg_dom, fqdn_dom in all_domains_to_check:
        dom_for_check = reg_dom or fqdn_dom
        if not dom_for_check:
            continue

        ext = _TLD_EXTRACTOR(dom_for_check)
        suffix = ext.suffix.lower()

        # e) blocklisted_domain
        if "blocklisted_domain" not in seen_ids:
            if dom_for_check in BLOCKLIST_DOMAINS or fqdn_dom in BLOCKLIST_DOMAINS:
                sev = "high"
                if "urls" in unverified or "emails" in unverified:
                    sev = _downgrade_severity(sev)
                flags.append(Flag(
                    id="blocklisted_domain",
                    severity=sev,
                    evidence=source_token,
                    why_it_matters="This domain is recorded on fraud and scam blocklists.",
                ))
                seen_ids.add("blocklisted_domain")

        # c) lookalike_domain (only for claimed real companies)
        if company_entry is not None and "lookalike_domain" not in seen_ids:
            if dom_for_check not in official_domains and dom_for_check not in FREE_MAIL_DOMAINS:
                # Check for rapidfuzz similarity or alias containment
                is_lookalike = False
                for off_dom in official_domains:
                    if fuzz.ratio(dom_for_check, off_dom) >= LOOKALIKE_THRESHOLD:
                        is_lookalike = True
                        break

                if not is_lookalike:
                    # Check if domain contains company name or alias plus extra words (e.g. tcs-careers.in)
                    comp_name_lower = company_entry["name"].lower()
                    aliases = [a.lower() for a in company_entry.get("aliases", [])]
                    for target in [comp_name_lower] + aliases:
                        if target in dom_for_check and dom_for_check != target:
                            is_lookalike = True
                            break

                if is_lookalike:
                    sev = "high"
                    if "company" in unverified or "urls" in unverified:
                        sev = _downgrade_severity(sev)
                    flags.append(Flag(
                        id="lookalike_domain",
                        severity=sev,
                        evidence=source_token,
                        why_it_matters="The domain mimics a legitimate company's name or website to deceive applicants.",
                    ))
                    seen_ids.add("lookalike_domain")

        # d) suspicious_tld
        if "suspicious_tld" not in seen_ids:
            if suffix in SUSPICIOUS_TLDS:
                sev = "low"
                if "urls" in unverified:
                    sev = _downgrade_severity(sev)
                flags.append(Flag(
                    id="suspicious_tld",
                    severity=sev,
                    evidence=source_token,
                    why_it_matters=f"This domain uses a top-level domain (.{suffix}) frequently linked with short-lived scam portals.",
                ))
                seen_ids.add("suspicious_tld")

        # d) url_shortener
        if "url_shortener" not in seen_ids:
            if dom_for_check in SHORTENERS or fqdn_dom in SHORTENERS:
                sev = "medium"
                if "urls" in unverified:
                    sev = _downgrade_severity(sev)
                flags.append(Flag(
                    id="url_shortener",
                    severity=sev,
                    evidence=source_token,
                    why_it_matters="Link shorteners mask the real destination URL to bypass security screening.",
                ))
                seen_ids.add("url_shortener")

    # -------------------------------------------------------------------------
    # f) Keyword Rules
    # -------------------------------------------------------------------------
    for r in KEYWORD_RULES:
        rule_id = r["id"]
        if rule_id in seen_ids:
            continue

        for pat in r["patterns"]:
            m = pat.search(text)
            if m:
                sev = r["severity"]
                matched_snippet = m.group(0).strip()
                flags.append(Flag(
                    id=rule_id,
                    severity=sev,
                    evidence=matched_snippet,
                    why_it_matters=r["why"],
                ))
                seen_ids.add(rule_id)
                break

    return flags
