"""Reusable visual components for the SahiCheck Streamlit user interface.

Strictly escapes all untrusted text using html.escape to protect against XSS,
and uses predefined limits and display labels.
"""

import html
import json
from typing import Any
import streamlit as st
import limits


ID_TITLES: dict[str, str] = {
    # Keyword rules from data/rules.json
    "fee_demand": "Fee demand",
    "upi_or_bank_request": "UPI or bank payment request",
    "otp_request": "OTP or verification code request",
    "id_document_request": "Identity document request",
    "urgency": "Artificial urgency",
    "guaranteed_job_or_pay": "Guaranteed job or unrealistic pay",
    "no_interview": "No interview or direct selection",
    "offplatform_channel_only": "Off-platform chat only",
    # Domain rules
    "free_mail_hr": "Free personal email used by HR",
    "lookalike_domain": "Lookalike company domain",
    "suspicious_tld": "Suspicious top-level domain",
    "url_shortener": "Link shortener used",
    "blocklisted_domain": "Blocklisted scam domain",
    # Verifier checks
    "official_domain": "Official company domain",
}


def get_readable_title(raw_id: str) -> str:
    """Map rule or check ID to plain-English title with fallback."""
    if not raw_id:
        return "Unknown Check"
    return ID_TITLES.get(raw_id) or raw_id.replace("_", " ").strip().capitalize()


def escape(val: Any) -> str:
    """Escapes user and AI generated text to prevent HTML injection."""
    if val is None:
        return ""
    return html.escape(str(val))


def render_header() -> None:
    """Renders the top branding header, badge, and one-line tagline."""
    header_html = """
    <div class="sahi-header-container">
        <div class="sahi-badge">
            <span>🛡️ SMARTER JOB SEARCH. SAFER DECISIONS.</span>
        </div>
        <div class="sahi-title">
            <span>🛡️ SahiCheck</span>
        </div>
        <p class="sahi-tagline">Check a job offer before you pay or share anything.</p>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_notes() -> None:
    """Renders honest, transparent security and privacy disclosures."""
    notes_html = """
    <div class="sahi-notes-box">
        <strong>Important Safety & Privacy Disclosures:</strong>
        <ul>
            <li><strong>In-Memory Processing:</strong> Uploaded text and screenshots are processed in memory and never persistently stored.</li>
            <li><strong>Hosted AI Evaluation:</strong> Messages are inspected via a hosted AI model; never include sensitive personal information like Aadhaar, PAN, bank accounts, or OTPs.</li>
            <li><strong>Decision Guidance Only:</strong> SahiCheck provides threat indicator guidance, not legal advice, and cannot guarantee a job is genuine.</li>
        </ul>
    </div>
    """
    st.markdown(notes_html, unsafe_allow_html=True)


def render_extracted_details(extracted: dict, transcript: str = "") -> None:
    """Renders the entity extraction breakdown inside a formatted container."""
    company = escape(extracted.get("company", "")) or "Not specified"
    role = escape(extracted.get("role", "")) or "Not specified"
    pay = escape(extracted.get("pay", "")) or "Not specified"
    channel = escape(extracted.get("channel", "")) or "Not specified"

    emails = ", ".join(escape(e) for e in extracted.get("emails", [])) or "None detected"
    phones = ", ".join(escape(p) for p in extracted.get("phones", [])) or "None detected"
    urls = ", ".join(escape(u) for u in extracted.get("urls", [])) or "None detected"
    upi_ids = ", ".join(escape(u) for u in extracted.get("upi_ids", [])) or "None detected"
    amounts = ", ".join(escape(a) for a in extracted.get("amounts", [])) or "None detected"
    unverified = extracted.get("unverified_fields", [])

    st.markdown(
        f"""
        <div class="sahi-card">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 13px;">
                <div><strong>Company:</strong> {company}</div>
                <div><strong>Role:</strong> {role}</div>
                <div><strong>Pay / Stipend:</strong> {pay}</div>
                <div><strong>Communication Channel:</strong> {channel}</div>
                <div><strong>Emails:</strong> {emails}</div>
                <div><strong>Phones:</strong> {phones}</div>
                <div><strong>Web URLs:</strong> {urls}</div>
                <div><strong>UPI Handles:</strong> {upi_ids}</div>
                <div><strong>Amounts:</strong> {amounts}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if unverified:
        unverified_tags = ", ".join(f"<code>{escape(f)}</code>" for f in unverified)
        st.markdown(
            f"""
            <div style="margin-top: 8px; font-size: 12px; color: #663500; background: #ffdcc3; padding: 6px 10px; border-radius: 6px;">
                ⚠️ <strong>Unverified Fields:</strong> {unverified_tags} (could not be independently validated).
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_verdict_card(verdict: dict, preliminary: bool = False) -> None:
    """Renders the main verdict card, legitimacy score, and red flags."""
    raw_verdict = verdict.get("verdict", "SUSPICIOUS")
    display_label = limits.DISPLAY_LABELS.get(raw_verdict, "Caution")
    score = verdict.get("legitimacy_score", 50)
    summary = escape(verdict.get("summary", ""))
    coverage = escape(verdict.get("evidence_coverage", "low"))
    explanation_source = verdict.get("explanation_source", "")

    # Map raw verdict enum to corresponding color styling class
    card_class = {
        "SCAM": "verdict-scam",
        "SUSPICIOUS": "verdict-suspicious",
        "SAFE": "verdict-safe",
    }.get(raw_verdict, "verdict-suspicious")

    preliminary_pill = (
        '<div class="pill-preliminary">⚠️ Preliminary: red-flag checks only</div>'
        if preliminary
        else f'<div style="font-size: 12px; opacity: 0.9; margin-top: 4px;">Evidence coverage: <strong>{coverage.capitalize()}</strong></div>'
    )

    # Check for hard cap triggers in high-severity red flags
    red_flags = verdict.get("red_flags", [])
    has_hard_cap_flag = any(
        f.get("severity") == "high"
        and (
            f.get("id") in ("fee_demand", "otp_request", "id_document_request", "upi_or_bank_request")
            or "fee" in f.get("id", "").lower()
            or "upi" in f.get("id", "").lower()
        )
        for f in red_flags
    )

    hard_cap_html = (
        '<div class="hard-cap-note">🛑 Critical Risk: This result will not change after the remaining checks.</div>'
        if has_hard_cap_flag and preliminary
        else ""
    )

    final_reminder = (
        '<div class="reminder-note">ℹ️ Reminder: No red flags found does not mean the job is genuine. Verify with the links below.</div>'
        if not preliminary
        else ""
    )

    template_note = (
        '<div style="font-size: 11px; opacity: 0.85; margin-top: 4px;">ℹ️ Explanation written from fixed templates</div>'
        if explanation_source == "template" and not preliminary
        else ""
    )

    st.markdown(
        f"""
        <div class="verdict-card {card_class}">
            <div class="verdict-header-row">
                <div>
                    <h2 class="verdict-label">{escape(display_label)}</h2>
                    {preliminary_pill}
                </div>
                <div class="verdict-score">
                    Legitimacy score: {score}/100
                </div>
            </div>
            <p style="margin: 8px 0; font-size: 14px; line-height: 1.5;">{summary}</p>
            {template_note}
            {hard_cap_html}
            {final_reminder}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render detected red flags with human-readable titles
    if red_flags:
        st.markdown("<h4 style='font-size: 15px; margin: 16px 0 8px 0;'>Detected Red Flags</h4>", unsafe_allow_html=True)
        for flag in red_flags:
            raw_flag_id = flag.get("id", "Warning")
            flag_title = escape(get_readable_title(raw_flag_id))
            severity = flag.get("severity", "medium").lower()
            badge_class = f"badge-{severity}"
            evidence = escape(flag.get("evidence", ""))
            why = escape(flag.get("why_it_matters", ""))

            st.markdown(
                f"""
                <div class="flag-card">
                    <div class="flag-header">
                        <span class="flag-title">🚩 {flag_title}</span>
                        <span class="{badge_class}">{severity.upper()} SEVERITY</span>
                    </div>
                    <div class="flag-quote">“{evidence}”</div>
                    <p class="flag-why"><strong>Why this matters:</strong> {why}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_checks_table(checks: list[dict]) -> None:
    """Renders deterministic and web verification checks table."""
    if not checks:
        return

    st.markdown("<h4 style='font-size: 15px; margin: 16px 0 8px 0;'>Verification Checks</h4>", unsafe_allow_html=True)

    for chk in checks:
        raw_id = chk.get("id", "")
        name = escape(chk.get("name") or get_readable_title(raw_id))
        status = chk.get("status", "unavailable").lower()
        tier = escape(chk.get("tier", "supporting"))
        detail = escape(chk.get("detail", ""))

        if status == "passed":
            status_icon = "🟢 Passed"
            status_class = "check-status-passed"
        elif status == "failed":
            status_icon = "🔴 Failed"
            status_class = "check-status-failed"
        else:
            status_icon = "⚪ Unable to verify"
            status_class = "check-status-unavailable"

        st.markdown(
            f"""
            <div class="check-row">
                <div>
                    <span style="font-weight: 600; color: #0d1c2f;">{name}</span>
                    <span class="tier-badge" style="margin-left: 8px;">{tier}</span>
                    <div style="font-size: 12px; color: #44474d; margin-top: 2px;">{detail}</div>
                </div>
                <div class="{status_class}">
                    {status_icon}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_positive_signs(signs: list[str]) -> None:
    """Renders identified legitimacy or positive signs directly from payload."""
    if not signs:
        return

    st.markdown("<h4 style='font-size: 15px; margin: 16px 0 8px 0;'>Positive Indicators</h4>", unsafe_allow_html=True)
    for sign in signs:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: #005236; margin-bottom: 6px;">
                <span>✅</span> <span>{escape(sign)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_next_steps(steps: list[str]) -> None:
    """Renders action items and recommendations as an actionable checklist."""
    if not steps:
        return

    st.markdown("<h4 style='font-size: 15px; margin: 16px 0 8px 0;'>Recommended Next Steps</h4>", unsafe_allow_html=True)
    st.markdown('<div class="next-steps-container">', unsafe_allow_html=True)
    for step in steps:
        st.markdown(
            f"""
            <div class="step-item">
                <span style="color: #0d1c32; font-weight: bold;">☑</span>
                <span>{escape(step)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_verify_links(links: list[dict]) -> None:
    """Renders independent verification hyperlinks opening safely in new tabs."""
    if not links:
        return

    st.markdown(
        """
        <h4 style='font-size: 15px; margin: 16px 0 4px 0;'>Links to verify this employer</h4>
        <p style='font-size: 12px; color: #555; margin-bottom: 8px;'>These are starting points for your own checks; they are not counted in the result.</p>
        """,
        unsafe_allow_html=True,
    )
    links_html = ['<div class="verify-links-row">']
    for link in links:
        label = escape(link.get("label", "Verify"))
        url = escape(link.get("url", "#"))
        links_html.append(
            f'<a class="verify-btn" href="{url}" target="_blank" rel="noopener noreferrer">🔗 {label} ↗</a>'
        )
    links_html.append("</div>")
    st.markdown("".join(links_html), unsafe_allow_html=True)


def render_error_box(message: str) -> None:
    """Renders a friendly error box with retry suggestions."""
    st.markdown(
        f"""
        <div class="error-card">
            <h3 style="margin: 0 0 6px 0; font-size: 16px; font-weight: 700;">❌ Analysis Could Not Proceed</h3>
            <p style="margin: 0; font-size: 14px;">{escape(message)}</p>
            <p style="margin: 8px 0 0 0; font-size: 12px; opacity: 0.85;">💡 <em>Hint: Check your input or try clicking 'Try a sample' to test a standard offer verification.</em></p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Renders transparent footer indicating open-weight model details."""
    try:
        import llm
        model_name = getattr(llm, "last_model_used", None) or llm.get_last_model_used() or ""
    except Exception:
        model_name = ""

    if model_name:
        model_text = f"Model: {model_name} (open-weight, hosted via Gemini API)"
    else:
        model_text = "Model: Gemma (open-weight, hosted via Gemini API)"

    st.markdown(
        f'<div style="text-align: center; font-size: 12px; color: #777; margin-top: 32px; padding: 16px 0; border-top: 1px solid #e0e0e0;">{escape(model_text)}</div>',
        unsafe_allow_html=True,
    )


def render_diagnostics(transcript: str, extracted: dict, full_verdict: dict) -> None:
    """Renders debug/transparency expanders: Transcript, Extracted details, and Raw JSON."""
    with st.expander("📝 Transcript"):
        st.text(transcript or "No transcript recorded.")

    with st.expander("🔍 Extracted Details"):
        render_extracted_details(extracted)

    with st.expander("⚙️ Raw JSON"):
        st.code(json.dumps(full_verdict, indent=2, ensure_ascii=False), language="json")
