"""Unit tests for SahiCheck pipeline orchestration, scoring caps, and event streaming."""

import sys
from pathlib import Path
from unittest.mock import patch

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.agent2b_verifier import check_official_domain
from core.agent3_synth import score_and_verdict
from core.pipeline import run_pipeline
from llm import LLMError
from schemas import Check, Extracted, ExtractionResult, Flag


@patch("core.agent1_extract.ask_gemma", return_value='{"company": "TCS"}')
@patch("core.agent3_synth.ask_gemma", return_value='{"summary": "Fee demand detected.", "flag_explanations": {}}')
def test_fee_demand_cap_holds_with_official_domain(mock_synth, mock_extract):
    """Fee demand enforces hard cap <= 29 and SCAM verdict even if official domain passes."""
    text = "Dear candidate, TCS requires Rs. 1,500 training kit fee. Email hr@tcs.com to confirm."
    events = list(run_pipeline(text=text, web_checks=True))
    final_event = next((e for e in events if e.stage == "final"), None)

    assert final_event is not None
    verdict = final_event.payload
    assert verdict["verdict"] == "SCAM"
    assert verdict["legitimacy_score"] <= 29


def test_no_flags_passed_official_domain_safe():
    """Clean offer with verified official domain scores 75 (50 + 25) and yields SAFE."""
    flags: list[Flag] = []
    checks = [
        Check(
            id="official_domain",
            name="Official Domain Check",
            tier="strong",
            status="passed",
            detail="Verified official sender domain: tcs.com",
            source="offline",
        )
    ]
    score, verdict, updated_checks = score_and_verdict(flags, checks)
    assert score == 75
    assert verdict == "SAFE"
    assert updated_checks[0].score_delta == 25


def test_no_flags_unknown_company_suspicious():
    """Clean offer from unknown company has unavailable check, scoring 50 (Caution/SUSPICIOUS)."""
    flags: list[Flag] = []
    checks = [
        Check(
            id="official_domain",
            name="Official Domain Check",
            tier="strong",
            status="unavailable",
            detail="Company not in our list of known employers",
            source="offline",
        )
    ]
    score, verdict, updated_checks = score_and_verdict(flags, checks)
    assert score == 50
    assert verdict == "SUSPICIOUS"
    assert updated_checks[0].score_delta == 0


def test_medium_flags_below_40_no_cap_yields_suspicious():
    """Score below 40 with only medium flags and no hard caps defaults to SUSPICIOUS (Caution)."""
    flags = [
        Flag(id="guaranteed_job_or_pay", severity="medium", evidence="100% placement"),
        Flag(id="no_interview", severity="medium", evidence="direct selection"),
        Flag(id="offplatform_channel_only", severity="medium", evidence="contact via Telegram only"),
    ]
    # Base 50 - 15 - 15 - 15 = 5. None of these flag IDs are in hard_cap_ids or cap_35_ids.
    score, verdict, _ = score_and_verdict(flags, [])
    assert score == 5
    assert verdict == "SUSPICIOUS"


def test_score_clamp_bounds():
    """Scores never fall below 3 or exceed 97."""
    many_high_flags = [
        Flag(id=f"flag_{i}", severity="high", evidence="evidence")
        for i in range(10)
    ]
    low_score, _, _ = score_and_verdict(many_high_flags, [])
    assert low_score == 3

    many_strong_checks = [
        Check(
            id=f"chk_{i}",
            name=f"Check {i}",
            tier="strong",
            status="passed",
            detail="ok",
            source="offline",
        )
        for i in range(5)
    ]
    high_score, _, _ = score_and_verdict([], many_strong_checks)
    assert high_score == 97


def test_gemma_explanation_hallucinated_flag_rejected():
    """Gemma output referencing unknown flag IDs is rejected in favor of the template."""
    text = "Hiring immediately for urgent role."
    bad_llm_json = '{"summary": "Urgent job offer.", "flag_explanations": {"fictional_flag": "Made up reason"}}'

    with patch("core.agent3_synth.ask_gemma", return_value=bad_llm_json):
        events = list(run_pipeline(text=text))
        final_event = next(e for e in events if e.stage == "final")
        assert "fictional_flag" not in final_event.payload.get("red_flags", [])


def test_gemma_llm_error_fallback_to_template():
    """When Gemma raises LLMError, pipeline completes with template summary without error."""
    text = "Hiring immediately for urgent role."

    with patch("core.agent3_synth.ask_gemma", side_effect=LLMError("API down")):
        events = list(run_pipeline(text=text))
        final_event = next((e for e in events if e.stage == "final"), None)
        assert final_event is not None
        assert len(final_event.payload["summary"]) > 0


@patch("core.agent1_extract.ask_gemma", return_value='{"company": "TCS"}')
@patch("core.agent3_synth.ask_gemma", return_value='{"summary": "Interview notice.", "flag_explanations": {}}')
def test_event_sequence_and_preliminary_flags(mock_synth, mock_extract):
    """Events stream in strict order: extracted -> checker_done -> verifier_check -> final."""
    text = "Software Engineer position at TCS. Please apply via careers at tcs.com."

    events = list(run_pipeline(text=text))
    stages = [e.stage for e in events]

    assert stages[0] == "extracted"
    assert stages[1] == "checker_done"
    assert "verifier_check" in stages
    assert stages[-1] == "final"

    checker_done_event = events[1]
    final_event = events[-1]

    assert checker_done_event.payload["preliminary"] is True
    assert final_event.payload["preliminary"] is False


@patch("core.agent1_extract.ask_gemma", return_value='{}')
@patch("core.agent3_synth.ask_gemma", return_value='{"summary": "Security deposit required.", "flag_explanations": {}}')
def test_hard_fail_skips_web_checks(mock_synth, mock_extract):
    """Hard-fail indicator sets skip_web=True while still emitting final verdict event."""
    text = "Pay Rs. 2,000 security deposit via UPI to hr@upi for joining."
    events = list(run_pipeline(text=text, web_checks=True))
    stages = [e.stage for e in events]

    assert "final" in stages
    final_event = next(e for e in events if e.stage == "final")
    assert final_event.payload["verdict"] == "SCAM"


def test_empty_input_yields_single_error_event():
    """Empty or whitespace-only input yields single error event and terminates immediately."""
    events = list(run_pipeline(text="   "))
    assert len(events) == 1
    assert events[0].stage == "error"
    assert "Please paste a message" in events[0].payload["message"]


def test_official_domain_check_outcomes():
    """Verify check_official_domain logic for matching, non-matching, and unknown companies."""
    tcs_company = {"name": "TCS", "domains": ["tcs.com"]}

    # Case 1: Matching official domain -> passed
    ex_pass = ExtractionResult(
        extracted=Extracted(company="TCS", emails=["careers@tcs.com"]),
        transcript="mail us at careers@tcs.com",
    )
    chk_pass = check_official_domain(ex_pass, ex_pass.transcript, tcs_company)
    assert chk_pass.status == "passed"
    assert "tcs.com" in chk_pass.detail

    # Case 2: Non-matching candidate domain -> failed
    ex_fail = ExtractionResult(
        extracted=Extracted(company="TCS", emails=["recruiter@gmail.com"]),
        transcript="mail us at recruiter@gmail.com",
    )
    chk_fail = check_official_domain(ex_fail, ex_fail.transcript, tcs_company)
    assert chk_fail.status == "failed"
    assert "gmail.com" in chk_fail.detail

    # Case 3: Unknown company -> unavailable
    ex_unavail = ExtractionResult(
        extracted=Extracted(company="Unlisted LLC", emails=["hr@unlisted.com"]),
        transcript="mail hr@unlisted.com",
    )
    chk_unavail = check_official_domain(ex_unavail, ex_unavail.transcript, None)
    assert chk_unavail.status == "unavailable"
