"""Agent 2b: Verifier module executing registered checks within strict latency budgets."""

import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterator, Literal

import tldextract

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import limits
from core.agent2_checker import claimed_company
from schemas import Check, ExtractionResult, VerifyLink

_TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())


def _extract_candidate_domains(extraction: ExtractionResult) -> list[str]:
    """Extract registrable domains from all emails and URLs in extraction."""
    domains: set[str] = set()

    for email in extraction.extracted.emails:
        if "@" in email:
            d = email.rsplit("@", 1)[-1].strip()
            ext = _TLD_EXTRACTOR(d)
            reg = getattr(ext, "top_domain_under_public_suffix", None) or getattr(ext, "registered_domain", None) or d
            if reg:
                domains.add(reg.lower())

    for url in extraction.extracted.urls:
        ext = _TLD_EXTRACTOR(url)
        reg = getattr(ext, "top_domain_under_public_suffix", None) or getattr(ext, "registered_domain", None)
        if reg:
            domains.add(reg.lower())

    return sorted(list(domains))


def check_official_domain(
    extraction: ExtractionResult,
    text: str,
    claimed: dict[str, Any] | None,
) -> Check:
    """Verify whether sender domain or URLs match the claimed company's official domain."""
    candidate_domains = _extract_candidate_domains(extraction)

    if claimed is not None:
        official_domains = [d.lower() for d in claimed.get("domains", [])]
        matching = [d for d in candidate_domains if d in official_domains]

        if matching:
            status = "passed"
            detail = f"Verified official sender domain: {', '.join(matching)}"
        elif candidate_domains:
            status = "failed"
            detail = f"Sender domains ({', '.join(candidate_domains)}) do not match official {claimed['name']} domains ({', '.join(official_domains)})"
        else:
            status = "unavailable"
            detail = "No sender domain or link found to compare"
    else:
        status = "unavailable"
        detail = "Company not in our list of known employers"

    return Check(
        id="official_domain",
        name="Official Domain Check",
        tier="strong",
        status=status,
        detail=detail,
        source="offline",
        score_delta=0,  # Filled later by scoring engine
    )


# Registered check functions with metadata: (func, needs_web)
CHECK_REGISTRY: list[tuple[Callable[[ExtractionResult, str, dict[str, Any] | None], Check], bool]] = [
    (check_official_domain, False),
]


def run_verifier(
    extraction: ExtractionResult,
    text: str,
    web_checks: bool = True,
    skip_web: bool = False,
) -> Iterator[Check]:
    """Execute registered checks concurrently with strict timeout and latency guardrails."""
    claimed = claimed_company(extraction, text)

    # Filter checks based on web_checks and skip_web flags
    active_checks = []
    for fn, needs_web in CHECK_REGISTRY:
        if needs_web and (not web_checks or skip_web):
            continue
        active_checks.append((fn, needs_web))

    if not active_checks:
        return

    overall_deadline = time.time() + limits.VERIFIER_BUDGET_S

    with ThreadPoolExecutor(max_workers=min(len(active_checks), 4)) as executor:
        future_to_fn = {
            executor.submit(fn, extraction, text, claimed): fn
            for fn, _ in active_checks
        }

        for future in as_completed(future_to_fn):
            fn = future_to_fn[future]
            check_id = getattr(fn, "__name__", "unknown_check").replace("check_", "")
            check_name = check_id.replace("_", " ").title()

            remaining_budget = max(0.1, overall_deadline - time.time())
            timeout_for_check = min(float(limits.PER_CHECK_TIMEOUT_S), remaining_budget)

            try:
                result = future.result(timeout=timeout_for_check)
                yield result
            except TimeoutError:
                yield Check(
                    id=check_id,
                    name=check_name,
                    tier="supporting",
                    status="unavailable",
                    detail="timed out",
                    source="web" if any(n for f, n in active_checks if f == fn) else "offline",
                    score_delta=0,
                )
            except Exception:
                yield Check(
                    id=check_id,
                    name=check_name,
                    tier="supporting",
                    status="unavailable",
                    detail="could not run",
                    source="web" if any(n for f, n in active_checks if f == fn) else "offline",
                    score_delta=0,
                )


def evidence_coverage(checks: list[Check]) -> Literal["low", "medium", "high"]:
    """Compute evidence coverage based on the number of completed checks."""
    available_count = sum(1 for c in checks if c.status != "unavailable")
    if available_count >= 3:
        return "high"
    if available_count == 2:
        return "medium"
    return "low"


def build_verify_links(company: str, official_domains: list[str]) -> list[VerifyLink]:
    """Generate safe, authoritative verification links for candidate self-investigation."""
    comp_clean = company.strip()
    if not comp_clean:
        return [
            VerifyLink(label="National Cyber Crime Portal", url="https://cybercrime.gov.in")
        ]

    encoded = urllib.parse.quote_plus(comp_clean)
    links = [
        VerifyLink(label="LinkedIn Company Page", url=f"https://www.linkedin.com/search/results/companies/?keywords={encoded}"),
        VerifyLink(label="Glassdoor Reviews", url=f"https://www.glassdoor.co.in/Search/results.htm?keyword={encoded}"),
        VerifyLink(label="AmbitionBox Company Profile", url=f"https://www.ambitionbox.com/search?keyword={encoded}"),
        VerifyLink(label="Google Scam Search", url=f"https://www.google.com/search?q={urllib.parse.quote_plus(comp_clean + ' scam')}"),
        VerifyLink(label="Ministry of Corporate Affairs (MCA)", url="https://www.mca.gov.in/content/mca/global/en/mca/master-data/MDS.html"),
    ]

    if official_domains:
        links.append(VerifyLink(label="Official Company Website", url=f"https://{official_domains[0]}"))

    links.append(VerifyLink(label="National Cyber Crime Portal", url="https://cybercrime.gov.in"))
    return links
