"""Smoke test script executing pipeline on 3 representative scenarios using real API."""

import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import limits
import llm
from core import agent3_synth
from core.pipeline import run_pipeline


def run_test_case(name: str, text: str) -> None:
    start_time = time.time()
    events = list(run_pipeline(text=text, web_checks=True))
    elapsed = time.time() - start_time

    final_event = next((e for e in events if e.stage == "final"), None)
    if not final_event:
        error_event = next((e for e in events if e.stage == "error"), None)
        err_msg = error_event.payload.get("message", "Unknown error") if error_event else "No final event"
        print(f"[{name}] FAILED: {err_msg}")
        return

    verdict_dict = final_event.payload
    raw_verdict = verdict_dict.get("verdict", "")
    display_label = limits.DISPLAY_LABELS.get(raw_verdict, raw_verdict)
    score = verdict_dict.get("legitimacy_score", 0)
    flags_count = len(verdict_dict.get("red_flags", []))
    model_used = getattr(llm, "last_model_used", None) or llm.get_last_model_used() or "None"
    explanation_source = agent3_synth.get_last_explanation_source()

    print(f"--- {name} ---")
    print(f"Verdict Label:       {display_label}")
    print(f"Legitimacy Score:    {score}")
    print(f"Number of Flags:     {flags_count}")
    print(f"Time Taken:          {elapsed:.2f}s")
    print(f"Model Used:          {model_used}")
    print(f"Explanation Source:  {explanation_source}")
    print()


def main() -> None:
    print("Running SahiCheck Backend Smoke Test (3 scenarios)...\n")

    # 1. Fee scam text
    scam_text = (
        "Dear Candidate, shortlisted for Data Entry job at Apex Global. "
        "Pay Rs 1,500 registration fee via UPI to hr@upi to get offer letter."
    )
    run_test_case("1. Fee Scam Sample", scam_text)

    # 2. Official TCS message
    tcs_text = (
        "Hello, this is regarding your interview at TCS. "
        "Please visit tcs.com/careers or contact careers@tcs.com for next steps."
    )
    run_test_case("2. Official TCS Sample", tcs_text)

    # 3. Plain neutral message
    neutral_text = (
        "We are looking for Python developers with 2 years of experience. "
        "Interested applicants can send their resumes for evaluation."
    )
    run_test_case("3. Plain Neutral Sample", neutral_text)


if __name__ == "__main__":
    main()
