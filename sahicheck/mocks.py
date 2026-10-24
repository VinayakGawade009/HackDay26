"""Mock pipeline generator for SahiCheck hackathon testing.

Simulates the backend pipeline stages with realistic latency and validates
all event payloads against Pydantic schema models before yielding.
"""

import time
from typing import Iterator
from schemas import (
    Check,
    Extracted,
    Flag,
    PipelineEvent,
    Verdict,
    VerifyLink,
)


def run_pipeline(
    text: str | None,
    image_bytes: bytes | None = None,
    image_mime: str = "image/png",
    web_checks: bool = True,
) -> Iterator[PipelineEvent]:
    """Simulates progressive pipeline execution with typed event yields.

    Selects a deterministic scenario based on input keywords or flags errors
    when inputs are empty or explicitly forced.
    """
    cleaned = (text or "").strip().lower()

    # 1. Validation: Reject completely empty submissions
    if not cleaned and not image_bytes:
        yield PipelineEvent(
            stage="error",
            payload={"message": "No job offer text or image provided. Please paste an offer or upload a screenshot."},
        )
        return

    # 2. Test hook: Force error scenario for UI error-state testing
    if "force-error" in cleaned:
        yield PipelineEvent(
            stage="error",
            payload={"message": "Simulated pipeline failure triggered by 'force-error' keyword."},
        )
        return

    # 3. Determine simulation scenario from input keywords
    is_scam = any(k in cleaned for k in ("fee", "deposit", "registration", "upi"))
    is_safe = "tcs.com" in cleaned

    # Helper to extract a relevant snippet from the user text if available
    def extract_snippet(keywords: tuple[str, ...], default_text: str) -> str:
        if text:
            for line in text.splitlines():
                if any(kw in line.lower() for kw in keywords):
                    return line.strip()
        return default_text

    # Scenario A: SCAM scenario (Detected advance fees, personal UPI, informal chat)
    if is_scam:
        extracted = Extracted(
            company="Apex Global Solutions",
            role="Work-from-Home Data Assistant",
            pay="Rs. 45,000 / month",
            channel="Telegram / WhatsApp",
            emails=["hr-apex@gmail.com"],
            phones=["+91-9876543210"],
            urls=["https://t.me/ApexHR_Instant"],
            upi_ids=["hr-apex@upi"],
            amounts=["Rs. 1,500", "Rs. 45,000"],
            unverified_fields=["company_registration", "recruiter_identity"],
        )
        fee_evidence = extract_snippet(
            ("fee", "deposit", "registration", "1,500", "1500"),
            "Mandatory Rs. 1,500 refundable security deposit for onboarding kit",
        )
        upi_evidence = extract_snippet(
            ("upi", "gpay", "phonepe", "paytm"),
            "Please deposit Rs. 1,500 registration charge via UPI to hr-apex@upi",
        )
        red_flags = [
            Flag(
                id="fee_demand",
                severity="high",
                evidence=fee_evidence,
                why_it_matters="Legitimate employers never demand registration, training, security deposit, or kit fees from candidates.",
            ),
            Flag(
                id="upi_or_bank_request",
                severity="high",
                evidence=upi_evidence,
                why_it_matters="Demands to send money via personal UPI handles, payment apps, or bank accounts are a hallmark of job scams.",
            ),
            Flag(
                id="free_mail_hr",
                severity="medium",
                evidence="hr-apex@gmail.com",
                why_it_matters="Official corporate recruiters communicate from company domains, not free public webmail accounts.",
            ),
            Flag(
                id="offplatform_channel_only",
                severity="medium",
                evidence="Telegram: @ApexHR_Instant",
                why_it_matters="Conducting recruitment strictly through Telegram or WhatsApp avoids scrutiny and legal accountability.",
            ),
        ]
        checks = [
            Check(
                id="official_domain",
                name="Company Domain & Web Identity",
                tier="strong",
                status="unavailable",
                detail="Company not in our list of known employers",
                source="web",
                score_delta=0,
            )
        ]
        next_steps = [
            "Do not transfer any money, registration fees, or onboarding kit charges.",
            "Do not share your Aadhaar, PAN card, bank details, or OTP with unverified contacts.",
            "Search company credentials on the official Ministry of Corporate Affairs (MCA) portal.",
            "If funds were already transferred, report immediately at https://cybercrime.gov.in or dial 1930.",
        ]
        verify_links = [
            VerifyLink(
                label="Search LinkedIn",
                url="https://www.linkedin.com/search/results/all/?keywords=Apex%20Global%20Solutions",
            ),
            VerifyLink(
                label="Search Glassdoor",
                url="https://www.glassdoor.com/Search/results.htm?keyword=Apex%20Global%20Solutions",
            ),
            VerifyLink(
                label="Search AmbitionBox",
                url="https://www.ambitionbox.com/overview/company-reviews",
            ),
            VerifyLink(
                label="Google 'Company Scam'",
                url="https://www.google.com/search?q=Apex+Global+Solutions+job+scam",
            ),
            VerifyLink(
                label="MCA Company Search",
                url="https://www.mca.gov.in/mcafoportal/findCompanyInfo.do",
            ),
            VerifyLink(
                label="National Cyber Crime Portal",
                url="https://cybercrime.gov.in",
            ),
        ]
        verdict_type = "SCAM"
        score = 14
        summary = "Critical fraud indicators detected: upfront payment demand via UPI and off-platform communication. Genuine employers do not charge onboarding or registration fees."
        positive_signs: list[str] = []

    # Scenario B: SAFE scenario (Verified employer domain tcs.com, no red flags)
    elif is_safe:
        extracted = Extracted(
            company="Tata Consultancy Services",
            role="Software Engineer",
            pay="Industry standard",
            channel="Official Careers Portal",
            emails=["careers@tcs.com"],
            phones=[],
            urls=["https://www.tcs.com/careers"],
            upi_ids=[],
            amounts=[],
            unverified_fields=[],
        )
        red_flags = []
        checks = [
            Check(
                id="official_domain",
                name="Company Domain & Web Identity",
                tier="strong",
                status="passed",
                detail="Verified legitimate official domain tcs.com matches corporate records",
                source="web",
                score_delta=25,
            )
        ]
        positive_signs = [
            "Official corporate domain (tcs.com) matches authentic corporate registry records.",
            "No upfront payment, registration fee, or security deposit requested.",
            "Standard recruitment communication through verified corporate infrastructure.",
        ]
        next_steps = [
            "Verify the job requisition ID directly on the official TCS careers portal (tcs.com/careers).",
            "Ensure all recruiter communications originate from an authentic @tcs.com email address.",
            "Never share banking OTPs, PINs, or confidential credentials under any circumstance.",
        ]
        verify_links = [
            VerifyLink(
                label="Official Careers Portal",
                url="https://www.tcs.com/careers",
            ),
            VerifyLink(
                label="TCS on LinkedIn",
                url="https://www.linkedin.com/company/tata-consultancy-services",
            ),
        ]
        verdict_type = "SAFE"
        score = 75
        summary = "No scam red flags found. The offer references a verified official corporate domain with no payment demands or unverified channels."

    # Scenario C: CAUTION scenario (Suspicious urgency and informal hiring)
    else:
        extracted = Extracted(
            company="Global Tech Outsourcing (Unverified)",
            role="Operations Coordinator",
            pay="Rs. 30,000 / month",
            channel="Direct Email / WhatsApp",
            emails=["hr@career-hiring.top"],
            phones=["+91-9123456789"],
            urls=["https://career-hiring.top"],
            upi_ids=[],
            amounts=["Rs. 30,000"],
            unverified_fields=["company_identity", "official_recruiter_status"],
        )
        red_flags = [
            Flag(
                id="urgency",
                severity="low",
                evidence="Offer expires within 24 hours, limited slots remaining",
                why_it_matters="Artificial urgency is used by recruiters to rush candidates into acting without verifying details.",
            ),
            Flag(
                id="no_interview",
                severity="medium",
                evidence="Direct selection confirmed without any formal technical interview",
                why_it_matters="Reputable employers evaluate candidates prior to formal offers; skipping interviews indicates high risk.",
            ),
        ]
        checks = [
            Check(
                id="official_domain",
                name="Company Domain & Web Identity",
                tier="strong",
                status="unavailable",
                detail="Company not in our list of known employers",
                source="web",
                score_delta=0,
            )
        ]
        positive_signs = []
        next_steps = [
            "Request a formal written offer letter issued from an official corporate domain.",
            "Verify the recruiter's identity on LinkedIn and cross-check company registration on MCA.",
            "Do not pay any advance fees or provide sensitive personal identification documents.",
        ]
        verify_links = [
            VerifyLink(label="Search LinkedIn", url="https://www.linkedin.com"),
            VerifyLink(label="Search Glassdoor", url="https://www.glassdoor.com"),
            VerifyLink(label="MCA Company Search", url="https://www.mca.gov.in"),
        ]
        verdict_type = "SUSPICIOUS"
        score = 50
        summary = "Unverified employer with signs of artificial urgency and informal recruitment. Proceed with heightened caution."

    transcript = text.strip() if text else "[Screenshot image processed for recruiter offer]"

    # Event 1: 'extracted' event with entity extraction and transcript
    time.sleep(0.8)
    yield PipelineEvent(
        stage="extracted",
        payload={
            "extracted": extracted.model_dump(),
            "transcript": transcript,
        },
    )

    # Event 2: 'checker_done' event with preliminary verdict from red flags
    time.sleep(0.8)
    preliminary_verdict = Verdict(
        verdict=verdict_type,
        legitimacy_score=score,
        evidence_coverage="low",
        summary=summary,
        red_flags=red_flags,
        checks=[],  # Preliminary has checks empty
        positive_signs=positive_signs,
        next_steps=next_steps,
        verify_links=verify_links,
        extracted=extracted,
        preliminary=True,
    )
    yield PipelineEvent(
        stage="checker_done",
        payload=preliminary_verdict.model_dump(),
    )

    # Event 3: 'verifier_check' events yielded individually per check
    for chk in checks:
        time.sleep(0.8)
        yield PipelineEvent(
            stage="verifier_check",
            payload=chk.model_dump(),
        )

    # Event 4: 'final' event with full report and preliminary=False
    time.sleep(0.8)
    final_verdict = Verdict(
        verdict=verdict_type,
        legitimacy_score=score,
        evidence_coverage="low",
        summary=summary,
        red_flags=red_flags,
        checks=checks,  # Full report includes checks
        positive_signs=positive_signs,
        next_steps=next_steps,
        verify_links=verify_links,
        extracted=extracted,
        preliminary=False,
    )
    yield PipelineEvent(
        stage="final",
        payload=final_verdict.model_dump(),
    )
