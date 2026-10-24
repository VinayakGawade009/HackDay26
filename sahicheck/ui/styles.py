"""Design system, fonts, and injected CSS styles for SahiCheck."""

import streamlit as st

CUSTOM_CSS = """
<style>
/* 1. Global Font and Typography */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="st-"], .stMarkdown, .stButton, .stTextArea, .stFileUploader, input, textarea, button {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
}

/* 2. Main Page Background & Container Sizing */
.stApp {
    background-color: #f8f9ff;
    color: #0d1c2f;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 960px !important;
}

/* 3. Hero Header Section */
.sahi-header-container {
    text-align: center;
    margin-bottom: 24px;
}

.sahi-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px;
    background-color: #ffdcc3;
    color: #663500;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 12px;
}

.sahi-title {
    font-size: 32px;
    font-weight: 800;
    color: #0d1c2f;
    letter-spacing: -0.02em;
    margin: 0 0 6px 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
}

.sahi-tagline {
    font-size: 15px;
    color: #44474d;
    margin: 0;
    font-weight: 500;
}

/* 4. Input Cards and Live Counter */
.sahi-card {
    background-color: #ffffff;
    border: 1px solid #c5c6cd;
    border-radius: 8px;
    padding: 18px;
    box-shadow: 0 1px 3px rgba(13, 28, 47, 0.04);
}

.char-counter {
    font-size: 12px;
    color: #44474d;
    text-align: right;
    margin-top: -12px;
    margin-bottom: 8px;
    font-family: monospace !important;
}

/* 5. Trust and Honest Notes Strip */
.sahi-notes-box {
    background-color: #e6eeff;
    border: 1px solid #c5c6cd;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 16px;
    margin-bottom: 24px;
    font-size: 13px;
    color: #44474d;
    line-height: 1.5;
}

.sahi-notes-box ul {
    margin: 6px 0 0 0;
    padding-left: 20px;
}

.sahi-notes-box li {
    margin-bottom: 4px;
}

/* 6. Verdict Cards (Categorized by Severity) */
.verdict-card {
    border-radius: 8px;
    padding: 22px;
    margin: 18px 0;
    box-shadow: 0 2px 8px rgba(13, 28, 47, 0.06);
}

.verdict-scam {
    background-color: #ffdad6;
    color: #93000a;
    border-left: 6px solid #ba1a1a;
}

.verdict-suspicious {
    background-color: #ffdcc3;
    color: #663500;
    border-left: 6px solid #904d00;
}

.verdict-safe {
    background-color: #6ffbbe;
    color: #005236;
    border-left: 6px solid #009668;
}

.verdict-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 12px;
}

.verdict-label {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.01em;
    margin: 0;
}

.verdict-score {
    font-size: 15px;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.6);
    padding: 6px 12px;
    border-radius: 6px;
    display: inline-block;
}

.pill-preliminary {
    display: inline-block;
    padding: 4px 10px;
    background-color: rgba(255, 255, 255, 0.8);
    border: 1px solid currentColor;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 6px;
}

.hard-cap-note {
    margin-top: 10px;
    font-weight: 700;
    font-size: 13px;
    color: #ba1a1a;
    background: rgba(255, 255, 255, 0.5);
    padding: 6px 10px;
    border-radius: 6px;
}

.reminder-note {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px dashed rgba(0, 0, 0, 0.15);
    font-size: 13px;
    font-weight: 600;
}

/* 7. Red Flags List */
.flag-card {
    background-color: #ffffff;
    border: 1px solid #c5c6cd;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 12px;
}

.flag-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.flag-title {
    font-size: 14px;
    font-weight: 700;
    color: #0d1c2f;
    margin: 0;
}

.badge-high {
    background-color: #ffdad6;
    color: #93000a;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
}

.badge-medium {
    background-color: #ffdcc3;
    color: #663500;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
}

.badge-low {
    background-color: #dde9ff;
    color: #0d1c32;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
}

.flag-quote {
    font-style: italic;
    background-color: #f8f9ff;
    border-left: 3px solid #ba1a1a;
    padding: 6px 10px;
    border-radius: 4px;
    margin: 6px 0;
    font-size: 13px;
    color: #0d1c2f;
}

.flag-why {
    font-size: 12px;
    color: #44474d;
    margin: 4px 0 0 0;
}

/* 8. Verification Checks Table */
.check-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background-color: #ffffff;
    border: 1px solid #c5c6cd;
    border-radius: 8px;
    margin-bottom: 8px;
    font-size: 13px;
}

.check-status-passed {
    color: #009668;
    font-weight: 700;
}

.check-status-failed {
    color: #ba1a1a;
    font-weight: 700;
}

.check-status-unavailable {
    color: #75777e;
    font-weight: 600;
}

.tier-badge {
    background-color: #dde9ff;
    color: #0d1c32;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
}

/* 9. Next Steps and Verify Links */
.next-steps-container {
    background-color: #ffffff;
    border: 1px solid #c5c6cd;
    border-radius: 8px;
    padding: 16px;
    margin-top: 14px;
}

.step-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #0d1c2f;
}

.verify-links-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 12px;
}

.verify-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background-color: #dde9ff;
    color: #0d1c32;
    border-radius: 8px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #c5c6cd;
    transition: background-color 0.15s ease;
}

.verify-btn:hover {
    background-color: #c5d8fc;
    color: #0d1c32;
    text-decoration: none;
}

/* 10. Streamlit Button Customization */
div.stButton > button[kind="primary"] {
    background-color: #0d1c32 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 0.6rem 1.4rem !important;
    border: none !important;
}

div.stButton > button[kind="primary"]:hover {
    background-color: #1a3254 !important;
    color: #ffffff !important;
}

div.stButton > button[kind="secondary"] {
    background-color: #ffffff !important;
    color: #0d1c32 !important;
    border: 1px solid #c5c6cd !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

div.stButton > button[kind="secondary"]:hover {
    background-color: #e6eeff !important;
}

/* 11. Error Card */
.error-card {
    background-color: #ffdad6;
    color: #93000a;
    border: 1px solid #ba1a1a;
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
}
</style>
"""


def inject_custom_styles() -> None:
    """Injects SahiCheck custom CSS stylesheets into Streamlit head."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
