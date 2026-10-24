"""Script to pre-generate data/cached_samples.json from the live pipeline for offline UI demo."""

import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import limits
from core.pipeline import run_pipeline

SAMPLES = [
    {
        "id": "sample_fee_scam",
        "label": "Fee Demand Scam",
        "text": (
            "Dear Candidate, You are shortlisted for Work-from-Home Data Assistant at Apex Global Solutions. "
            "Monthly stipend: Rs. 45,000. Please deposit Rs. 1,500 registration charge (refundable) via UPI "
            "to hr-apex@upi for onboarding kit allocation. Connect immediately on Telegram: @ApexHR_Instant "
            "to receive your appointment letter."
        ),
    },
    {
        "id": "sample_tcs_interview",
        "label": "Official TCS Interview",
        "text": (
            "Hello, this is regarding your interview at TCS. "
            "Please visit tcs.com/careers or contact careers@tcs.com for next steps. "
            "Bring your original documents on the joining day."
        ),
    },
    {
        "id": "sample_neutral_recruiter",
        "label": "Neutral Recruiter Message",
        "text": (
            "We are looking for Python developers with 2 years of experience. "
            "Interested applicants can send their resumes for evaluation."
        ),
    },
]


def main() -> None:
    print("Generating data/cached_samples.json via core.pipeline...\n")
    cached_list = []

    for item in SAMPLES:
        sample_id = item["id"]
        sample_label = item["label"]
        sample_text = item["text"]

        events = []
        has_error = False

        for evt in run_pipeline(text=sample_text, web_checks=True):
            if evt.stage == "error":
                has_error = True
                print(f"Skipping sample '{sample_label}' (ended in error event: {evt.payload.get('message')})")
                break
            events.append({"stage": evt.stage, "payload": evt.payload})

        if has_error or not events:
            continue

        final_evt = next((e for e in events if e["stage"] == "final"), None)
        verdict_label = "Unknown"
        if final_evt:
            raw_v = final_evt["payload"].get("verdict", "")
            verdict_label = limits.DISPLAY_LABELS.get(raw_v, raw_v)

        cached_list.append({
            "id": sample_id,
            "label": sample_label,
            "text": sample_text,
            "events": events,
        })
        print(f"Sample: {sample_label} | Events: {len(events)} | Verdict: {verdict_label}")

    output_path = Path(ROOT_DIR) / "data" / "cached_samples.json"
    output_path.write_text(json.dumps(cached_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSuccessfully wrote {len(cached_list)} cached sample(s) to {output_path}")


if __name__ == "__main__":
    main()
