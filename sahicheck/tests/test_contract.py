"""Contract tests ensuring run_pipeline event sequence and payload specifications."""

import sys
from pathlib import Path
from unittest.mock import patch

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.pipeline import run_pipeline


@patch("core.agent1_extract.ask_gemma", return_value='{"company": "TCS", "role": "Developer"}')
@patch("core.agent3_synth.ask_gemma", return_value='{"summary": "Verified company posting.", "flag_explanations": {}}')
def test_pipeline_contract_standard_order(mock_synth_llm, mock_extract_llm):
    """Pipeline yields events in strict contract order with exact schema requirements."""
    text = "We are hiring software engineers at TCS. Visit https://tcs.com to apply."

    events = list(run_pipeline(text=text, web_checks=True))
    stages = [e.stage for e in events]

    # 1. Order: extracted, checker_done, verifier_check (zero or more), final
    assert stages[0] == "extracted"
    assert stages[1] == "checker_done"

    verifier_indices = [i for i, s in enumerate(stages) if s == "verifier_check"]
    if verifier_indices:
        assert verifier_indices[0] == 2
        assert verifier_indices[-1] < len(stages) - 1

    assert stages[-1] == "final"

    # 2. Every payload is a plain dict
    for e in events:
        assert isinstance(e.payload, dict), f"Payload for stage {e.stage} must be dict"

    # 3. checker_done has preliminary=True and checks == []
    checker_done_payload = events[1].payload
    assert checker_done_payload.get("preliminary") is True
    assert checker_done_payload.get("checks") == []

    # 4. final has preliminary=False
    final_payload = events[-1].payload
    assert final_payload.get("preliminary") is False

    # 5. final contains all required contract keys
    required_keys = {
        "verdict",
        "legitimacy_score",
        "evidence_coverage",
        "summary",
        "red_flags",
        "checks",
        "positive_signs",
        "next_steps",
        "verify_links",
        "extracted",
    }
    assert required_keys.issubset(final_payload.keys())


@patch("core.agent1_extract.ask_gemma", return_value='{}')
@patch("core.agent3_synth.ask_gemma", return_value='{}')
def test_pipeline_contract_error_ends_stream(mock_synth, mock_extract):
    """Error event immediately terminates the event stream with no subsequent events."""
    # Test empty text
    events_empty = list(run_pipeline(text="   "))
    assert len(events_empty) == 1
    assert events_empty[0].stage == "error"
    assert isinstance(events_empty[0].payload, dict)
    assert "message" in events_empty[0].payload

    # Test disabled screenshot input
    events_img = list(run_pipeline(text="Some text", image_bytes=b"dummy_bytes"))
    assert len(events_img) == 1
    assert events_img[0].stage == "error"
    assert isinstance(events_img[0].payload, dict)
    assert "message" in events_img[0].payload


@patch("core.agent1_extract.ask_gemma", return_value='{"company": "Apex Global"}')
@patch("core.agent3_synth.ask_gemma", return_value='{"summary": "Fee scam detected.", "flag_explanations": {}}')
def test_pipeline_contract_scam_flow(mock_synth, mock_extract):
    """Hard-fail scam flow conforms to identical dictionary structure and contract order."""
    text = "Shortlisted for Data Entry. Pay Rs 1,500 registration fee via UPI."

    events = list(run_pipeline(text=text, web_checks=True))
    stages = [e.stage for e in events]

    assert stages[0] == "extracted"
    assert stages[1] == "checker_done"
    assert stages[-1] == "final"

    for e in events:
        assert isinstance(e.payload, dict)

    assert events[1].payload.get("preliminary") is True
    assert events[-1].payload.get("preliminary") is False
    assert events[-1].payload.get("verdict") == "SCAM"
