"""Session state management, rate-limiting, and run guards for SahiCheck."""

import time
import streamlit as st
import limits

# Built-in sample fee-scam text for quick user testing
SAMPLE_FEE_SCAM = (
    "Dear Candidate, You are shortlisted for Work-from-Home Data Assistant at Apex Global Solutions. "
    "Monthly stipend: Rs. 45,000. Please deposit Rs. 1,500 registration charge (refundable) via UPI "
    "to hr-apex@upi for onboarding kit allocation. Connect immediately on Telegram: @ApexHR_Instant "
    "to receive your appointment letter."
)


def init_session_state() -> None:
    """Initializes all required session state keys with default values."""
    if "run_id" not in st.session_state:
        st.session_state.run_id = 0
    if "is_running" not in st.session_state:
        st.session_state.is_running = False
    if "submission_history" not in st.session_state:
        st.session_state.submission_history = []
    if "user_text" not in st.session_state:
        st.session_state.user_text = ""
    if "web_checks_enabled" not in st.session_state:
        st.session_state.web_checks_enabled = True


def check_rate_limit() -> tuple[bool, str]:
    """Enforces MAX_SUBMISSIONS_PER_HOUR per user session.

    Cleans up timestamps older than 1 hour and rejects runs if limit is exceeded.
    """
    now = time.time()
    one_hour_ago = now - 3600.0

    # Retain only timestamps from the last 60 minutes
    recent = [t for t in st.session_state.submission_history if t > one_hour_ago]
    st.session_state.submission_history = recent

    if len(recent) >= limits.MAX_SUBMISSIONS_PER_HOUR:
        return (
            False,
            f"You have reached the maximum limit of {limits.MAX_SUBMISSIONS_PER_HOUR} checks per hour. "
            "Please wait a few minutes before submitting another check.",
        )

    return True, ""


def record_submission() -> None:
    """Records the timestamp of a new verified submission."""
    st.session_state.submission_history.append(time.time())


def start_run() -> int:
    """Begins a new pipeline run, increments run_id, and sets is_running guard."""
    st.session_state.run_id += 1
    st.session_state.is_running = True
    return st.session_state.run_id


def finish_run() -> None:
    """Clears the is_running flag once the pipeline stream terminates."""
    st.session_state.is_running = False


def is_current_run(run_id: int) -> bool:
    """Validates whether a yielding event belongs to the currently active run."""
    return st.session_state.run_id == run_id
