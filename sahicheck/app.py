"""SahiCheck: Scam Detection UI for Job Offers.

A fast, transparent Streamlit application that evaluates recruitment offers
for fraud indicators using progressive streaming events.
"""

import json
import os
import time
from pathlib import Path
import streamlit as st

import limits
from schemas import PipelineEvent
from ui.components import (
    render_checks_table,
    render_diagnostics,
    render_error_box,
    render_extracted_details,
    render_footer,
    render_header,
    render_next_steps,
    render_notes,
    render_positive_signs,
    render_verdict_card,
    render_verify_links,
)
from ui.state import (
    SAMPLE_FEE_SCAM,
    check_rate_limit,
    finish_run,
    init_session_state,
    is_current_run,
    record_submission,
    start_run,
)
from ui.styles import inject_custom_styles

# 1. Page Configuration and Theme Ingestion
st.set_page_config(
    page_title="SahiCheck — Job Offer Scam Checker",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="collapsed",
)
inject_custom_styles()
init_session_state()


def get_pipeline():
    """Import pipeline function. Defaults to real core.pipeline unless USE_MOCKS=1 is explicitly set."""
    use_mocks = os.getenv("USE_MOCKS", "0").strip().lower() in ("1", "true", "yes")
    if use_mocks:
        try:
            from mocks import run_pipeline

            return run_pipeline, True
        except Exception:
            return None, True

    try:
        from core.pipeline import run_pipeline

        return run_pipeline, False
    except Exception:
        # Never silently fallback to mocks
        return None, False


def find_cached_sample(raw_text: str) -> list[dict] | None:
    """Checks data/cached_samples.json for matching text to replay stored events."""
    cached_file = Path("data/cached_samples.json")
    if not cached_file.exists():
        return None
    try:
        raw_json = cached_file.read_text(encoding="utf-8").strip()
        if not raw_json:
            return None
        samples = json.loads(raw_json)
        if not isinstance(samples, list) or not samples:
            return None
        for item in samples:
            if isinstance(item, dict) and item.get("text", "").strip() == raw_text.strip():
                events = item.get("events")
                if isinstance(events, list) and events:
                    return events
    except Exception:
        return None
    return None


# 2. Main Page Header
render_header()

# Check pipeline availability or mock status
pipeline_fn, is_mock = get_pipeline()
if is_mock:
    st.warning("Demo mode: sample data, not a real check.")
elif pipeline_fn is None:
    render_error_box("The checker is not available right now.")
    st.stop()

# 3. Two-Column Input Layout (Stacked on Mobile)
col_text, col_upload = st.columns([1, 1], gap="medium")

with col_text:
    st.markdown("<strong>📝 Paste Offer Text</strong>", unsafe_allow_html=True)
    current_text = st.text_area(
        label="Paste message or offer text",
        key="offer_text_input",
        placeholder="Paste a recruiter message, job description, email, or offer details...",
        height=180,
        label_visibility="collapsed",
    )
    char_count = len(current_text or "")
    st.markdown(
        f'<div class="char-counter">{char_count:,} / {limits.MAX_TEXT_CHARS:,} characters</div>',
        unsafe_allow_html=True,
    )

with col_upload:
    st.markdown("<strong>🖼️ Upload Screenshot</strong>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        label="Upload screenshot image",
        type=["png", "jpg", "jpeg"],
        key="offer_image_input",
        label_visibility="collapsed",
    )
    st.markdown(
        f'<div class="char-counter">PNG or JPG, up to {limits.MAX_IMAGE_MB} MB</div>',
        unsafe_allow_html=True,
    )


def populate_sample() -> None:
    """Callback triggered before widget instantiation to populate sample text."""
    st.session_state["offer_text_input"] = SAMPLE_FEE_SCAM


# 4. Action Controls Row
ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.5, 1, 1], gap="small")

with ctrl_col1:
    web_checks = st.toggle("Run web checks", value=True, help="Cross-checks official domain records and registries.")

with ctrl_col2:
    st.button("Try a sample", on_click=populate_sample, use_container_width=True)

with ctrl_col3:
    check_clicked = st.button(
        "Check this offer",
        type="primary",
        disabled=st.session_state.is_running,
        use_container_width=True,
    )

# 5. Security and Privacy Honest Notes
render_notes()

# 6. Progressive Execution Placeholders
status_placeholder = st.empty()
extracted_placeholder = st.empty()
verdict_placeholder = st.empty()
checks_placeholder = st.empty()
final_placeholder = st.empty()
diagnostics_placeholder = st.empty()
error_placeholder = st.empty()

# 7. Submission Processing and Streaming Loop
if check_clicked:
    raw_text = (st.session_state.get("offer_text_input") or "").strip()
    image_bytes = uploaded_file.getvalue() if uploaded_file else None
    image_mime = uploaded_file.type if (uploaded_file and uploaded_file.type) else "image/png"

    # Input validation: Length constraint
    if len(raw_text) > limits.MAX_TEXT_CHARS:
        error_placeholder.error(
            f"Input text exceeds the maximum limit of {limits.MAX_TEXT_CHARS:,} characters. Please shorten your text."
        )
        st.stop()

    # Input validation: File size constraint
    if uploaded_file and uploaded_file.size > limits.MAX_IMAGE_MB * 1024 * 1024:
        error_placeholder.error(
            f"Uploaded file exceeds the {limits.MAX_IMAGE_MB} MB size limit. Please upload a smaller image."
        )
        st.stop()

    # Input validation: Ensure at least one input is provided
    if not raw_text and not image_bytes:
        error_placeholder.warning("Please paste offer text or upload a screenshot to proceed with verification.")
        st.stop()

    # Session Guard: Rate limiting checks per hour
    rate_ok, rate_msg = check_rate_limit()
    if not rate_ok:
        error_placeholder.error(rate_msg)
        st.stop()

    record_submission()
    current_run = start_run()

    # Streaming state containers
    checks_accumulated: list[dict] = []
    extracted_data: dict = {}
    transcript_text: str = ""
    pipeline_succeeded = False
    pipeline_errored = False

    try:
        # Check first for cached verified sample replay
        cached_events = find_cached_sample(raw_text)
        if cached_events:
            status_placeholder.info("Replaying verified sample analysis...")
            for cached_raw in cached_events:
                time.sleep(0.5)
                c_stage = cached_raw.get("stage")
                c_payload = cached_raw.get("payload", {})

                if c_stage == "extracted":
                    extracted_data = c_payload.get("extracted", {})
                    transcript_text = c_payload.get("transcript", "")
                    with extracted_placeholder.expander("🔍 Extracted Details", expanded=False):
                        render_extracted_details(extracted_data, transcript_text)
                elif c_stage == "checker_done":
                    with verdict_placeholder.container():
                        render_verdict_card(c_payload, preliminary=True)
                elif c_stage == "verifier_check":
                    checks_accumulated.append(c_payload)
                    with checks_placeholder.container():
                        render_checks_table(checks_accumulated)
                elif c_stage == "final":
                    pipeline_succeeded = True
                    verdict_placeholder.empty()
                    elapsed_val = c_payload.get("elapsed_s", 0.5)
                    status_placeholder.success(f"Checked in {elapsed_val} seconds")
                    with final_placeholder.container():
                        render_verdict_card(c_payload, preliminary=False)
                        if checks_accumulated:
                            render_checks_table(checks_accumulated)
                        if c_payload.get("positive_signs"):
                            render_positive_signs(c_payload["positive_signs"])
                        if c_payload.get("next_steps"):
                            render_next_steps(c_payload["next_steps"])
                        if c_payload.get("verify_links"):
                            render_verify_links(c_payload["verify_links"])
                    with diagnostics_placeholder.container():
                        render_diagnostics(transcript_text, extracted_data, c_payload)
                    break
        else:
            status_placeholder.info("Analyzing offer... This can take up to a minute.")
            event_stream = pipeline_fn(
                text=raw_text or None,
                image_bytes=image_bytes,
                image_mime=image_mime,
                web_checks=web_checks,
            )

            for event in event_stream:
                if not is_current_run(current_run):
                    break

                stage = event.stage
                payload = event.payload

                # Stage 1: Extracted entities
                if stage == "extracted":
                    status_placeholder.info("Checking red flags... This can take up to a minute.")
                    extracted_data = payload.get("extracted", {})
                    transcript_text = payload.get("transcript", "")
                    with extracted_placeholder.expander("🔍 Extracted Details", expanded=False):
                        render_extracted_details(extracted_data, transcript_text)

                # Stage 2: Preliminary verdict from red flags
                elif stage == "checker_done":
                    status_placeholder.info("Verifying the company... This can take up to a minute.")
                    with verdict_placeholder.container():
                        render_verdict_card(payload, preliminary=True)

                # Stage 3: Verification checks
                elif stage == "verifier_check":
                    checks_accumulated.append(payload)
                    with checks_placeholder.container():
                        render_checks_table(checks_accumulated)

                # Stage 4: Final verdict report
                elif stage == "final":
                    pipeline_succeeded = True
                    verdict_placeholder.empty()

                    elapsed_val = payload.get("elapsed_s")
                    if elapsed_val:
                        status_placeholder.success(f"Checked in {elapsed_val} seconds")
                    else:
                        status_placeholder.empty()

                    with final_placeholder.container():
                        render_verdict_card(payload, preliminary=False)
                        if checks_accumulated:
                            render_checks_table(checks_accumulated)
                        if payload.get("positive_signs"):
                            render_positive_signs(payload["positive_signs"])
                        if payload.get("next_steps"):
                            render_next_steps(payload["next_steps"])
                        if payload.get("verify_links"):
                            render_verify_links(payload["verify_links"])

                    with diagnostics_placeholder.container():
                        render_diagnostics(transcript_text, extracted_data, payload)
                    break

                # Stage 5: Error event
                elif stage == "error":
                    pipeline_errored = True
                    status_placeholder.empty()
                    verdict_placeholder.empty()
                    checks_placeholder.empty()
                    with error_placeholder.container():
                        render_error_box(payload.get("message", "Verification could not be completed."))
                    break

        if not pipeline_succeeded and not pipeline_errored and is_current_run(current_run):
            status_placeholder.empty()
            with error_placeholder.container():
                render_error_box(
                    "The verification process ended unexpectedly without producing a final report. Please try again."
                )

    finally:
        finish_run()

# 8. Honest Model Attributions Footer
render_footer()
