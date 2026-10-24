"""Unit tests for SahiCheck deterministic extraction, validation, and rule checking."""

import sys
from pathlib import Path
from unittest.mock import patch

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.agent1_extract import extract, _extract_regex
from core.agent2_checker import run_checker
from llm import LLMError
from schemas import Extracted, ExtractionResult


def test_fee_demand_english():
    """English fee demand text flags fee_demand with high severity."""
    text = "Dear candidate, please pay registration fee of Rs. 1,500 to confirm your seat."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    flag = next((f for f in flags if f.id == "fee_demand"), None)
    assert flag is not None
    assert flag.severity == "high"


def test_fee_demand_hinglish():
    """Hinglish fee demand text flags fee_demand."""
    text = "Aapko registration fees jama karo training shuru karne ke liye."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    flag = next((f for f in flags if f.id == "fee_demand"), None)
    assert flag is not None


def test_upi_request():
    """Direct UPI payment request flags upi_or_bank_request."""
    text = "Send the processing charges via UPI to hr-recruitment@upi."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    assert any(f.id == "upi_or_bank_request" for f in flags)


def test_otp_request():
    """Requesting an OTP verification code flags otp_request."""
    text = "Please share the OTP received on your mobile to verify your job application."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    assert any(f.id == "otp_request" for f in flags)


def test_id_document_request_flagged():
    """Demanding photos of IDs over messaging flags id_document_request."""
    text = "Please send your Aadhaar and PAN photo on WhatsApp for instant offer letter."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    assert any(f.id == "id_document_request" for f in flags)


def test_id_document_request_not_flagged():
    """Asking candidates to bring originals on joining day does NOT flag id_document_request."""
    text = "Please bring originals of Aadhaar and PAN on joining day for HR physical verification."
    extraction = ExtractionResult(extracted=Extracted(), transcript=text)
    flags = run_checker(extraction, text)
    assert not any(f.id == "id_document_request" for f in flags)


def test_free_mail_hr_tcs():
    """Claiming to be TCS while using a free Gmail address flags free_mail_hr with high severity."""
    text = "Selected for TCS! Please email hr.tcsrecruiter2024@gmail.com with your resume."
    extraction = ExtractionResult(
        extracted=Extracted(company="TCS", emails=["hr.tcsrecruiter2024@gmail.com"]),
        transcript=text,
    )
    flags = run_checker(extraction, text)
    flag = next((f for f in flags if f.id == "free_mail_hr"), None)
    assert flag is not None
    assert flag.severity == "high"


def test_lookalike_domain_tcs():
    """Domain mimicking TCS (tcs-careers.in) flags lookalike_domain with high severity."""
    text = "Official offer from TCS. Apply online at http://tcs-careers.in or mail hr@tcs-careers.in."
    extraction = ExtractionResult(
        extracted=Extracted(
            company="TCS",
            emails=["hr@tcs-careers.in"],
            urls=["http://tcs-careers.in"],
        ),
        transcript=text,
    )
    flags = run_checker(extraction, text)
    flag = next((f for f in flags if f.id == "lookalike_domain"), None)
    assert flag is not None
    assert flag.severity == "high"


def test_real_company_normal_domain():
    """Official tcs.com domain in a normal message flags neither lookalike nor free_mail."""
    text = "Thank you for interviewing at TCS. Your onboarding details will be sent from hr@tcs.com."
    extraction = ExtractionResult(
        extracted=Extracted(company="TCS", emails=["hr@tcs.com"]),
        transcript=text,
    )
    flags = run_checker(extraction, text)
    assert not any(f.id == "lookalike_domain" for f in flags)
    assert not any(f.id == "free_mail_hr" for f in flags)


def test_unknown_company_unusual_domain():
    """Unknown company with an unusual domain does NOT trigger lookalike_domain."""
    text = "Welcome to Starlight Solutions. Submit portfolio at http://starlight-hr-careers.biz."
    extraction = ExtractionResult(
        extracted=Extracted(company="Starlight Solutions", urls=["http://starlight-hr-careers.biz"]),
        transcript=text,
    )
    flags = run_checker(extraction, text)
    assert not any(f.id == "lookalike_domain" for f in flags)


def test_regex_upi_vs_email():
    """UPI ID (no dot in handle) and email (dot in domain) are never cross-classified."""
    text = "Send Rs. 500 to hr-apex@upi or contact hr@apex.com for support."
    regex_res = _extract_regex(text)
    assert "hr-apex@upi" in regex_res["upi_ids"]
    assert "hr-apex@upi" not in regex_res["emails"]
    assert "hr@apex.com" in regex_res["emails"]
    assert "hr@apex.com" not in regex_res["upi_ids"]


def test_extract_llm_error_fallback():
    """extract() returns deterministic regex results when ask_gemma raises LLMError."""
    with patch("core.agent1_extract.ask_gemma", side_effect=LLMError("API unreachable")):
        text = "Contact recruiter at hr@apex.com or pay Rs. 1,000 via UPI to payment@oksbi."
        res = extract(text=text)
        assert res.transcript == text
        assert "hr@apex.com" in res.extracted.emails
        assert "payment@oksbi" in res.extracted.upi_ids
        assert res.extracted.company == ""  # Graceful fallback without crashing


def test_extract_hallucinated_phone_dropped():
    """Model-returned phone numbers not literally in text are dropped by source check."""
    fake_json = '{"company": "Apex Corp", "phones": ["+919999999999"]}'
    with patch("core.agent1_extract.ask_gemma", return_value=fake_json):
        text = "Apex Corp is hiring a Data Entry specialist. Salary Rs 25,000."
        res = extract(text=text)
        assert "+919999999999" not in res.extracted.phones
        assert res.extracted.company == "Apex Corp"


def test_empty_text():
    """Empty text produces empty extraction and zero flags without crashing."""
    res = extract(text="")
    flags = run_checker(res, "")
    assert len(flags) == 0
    assert res.transcript == ""
    assert res.extracted.emails == []
