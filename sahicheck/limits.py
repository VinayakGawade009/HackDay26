"""Plain constants and thresholds for SahiCheck without logic."""

# Input constraints: prevents memory bloat and API token abuse
MAX_TEXT_CHARS = 5000
MAX_IMAGE_MB = 5
MAX_IMAGE_SIDE_PX = 1600

# LLM constraints: enforces bounded latency and graceful backoff
LLM_TIMEOUT_S = 30
LLM_MAX_RETRIES = 2
LLM_BACKOFF_S = 2

# Session constraints: rate limiting to prevent spam
MAX_SUBMISSIONS_PER_HOUR = 10

# Verifier constraints: bounded latency and bandwidth for external network checks
VERIFIER_BUDGET_S = 8
PER_CHECK_TIMEOUT_S = 3
MAX_DOMAINS = 3
MAX_OUTBOUND_REQUESTS = 4
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 200_000
DOMAIN_CACHE_TTL_S = 86_400

# Scoring engine: baseline score modified by rule and tier outcomes
SCORE_START = 50
SEVERITY_PENALTY = {"high": -30, "medium": -15, "low": -5}
TIER_PASS = {"strong": 25, "supporting": 10, "weak": 5}
TIER_FAIL = {"strong": -20, "supporting": -10, "weak": -5}

# Hard caps: severe red flags force score down regardless of positive signals
CAP_HARD_FAIL = 29  # Triggered by fee demands, OTP requests, ID-document requests
CAP_LOOKALIKE_OR_BLOCKLIST = 35

# Score boundaries and categorization bands
SCORE_MIN = 3
SCORE_MAX = 97
BAND_NO_RED_FLAGS = 70  # Score >= 70
BAND_CAUTION = 40       # Score 40-69; below 40 is high risk

# User-facing verdict labels (UI shows only these labels, never raw enums)
DISPLAY_LABELS = {
    "SAFE": "No red flags found",
    "SUSPICIOUS": "Caution",
    "SCAM": "High risk",
}
