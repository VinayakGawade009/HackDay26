"""Core multi-agent pipeline orchestrating extraction, rule checks, verification, and synthesis."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Iterator

# Resolve root directory imports
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import limits
from core.agent1_extract import extract
from core.agent2_checker import run_checker
from core.agent2b_verifier import run_verifier
from core.agent3_synth import (
    HARD_CAP_IDS,
    build_final,
    build_next_steps,
    score_and_verdict,
    template_explanation,
)
from schemas import PipelineEvent, Verdict

# In-memory result cache mapping SHA-256(normalized_text) -> list of (stage, payload_dict)
# NOTE: This cache is strictly memory-only (RAM), capped at 50 entries (LRU/FIFO),
# and is never written to disk, logged, or serialized.
_PIPELINE_CACHE: dict[str, list[tuple[str, dict]]] = {}
_MAX_PIPELINE_CACHE_SIZE = 50


def _normalize_text_for_cache(text: str) -> str:
    """Strip and collapse repeated whitespace runs for uniform cache key hashing."""
    return " ".join(text.split())


def run_pipeline(
    text: str | None,
    image_bytes: bytes | None = None,
    image_mime: str = "image/png",
    web_checks: bool = True,
) -> Iterator[PipelineEvent]:
    """Execute SahiCheck pipeline yielding sequential events for UI streaming."""
    # Input validation
    if image_bytes is not None:
        yield PipelineEvent(
            stage="error",
            payload={"message": "Screenshot input is not enabled yet"},
        )
        return

    if not text or not text.strip():
        yield PipelineEvent(
            stage="error",
            payload={"message": "Please paste a message or upload a screenshot."},
        )
        return

    if len(text) > limits.MAX_TEXT_CHARS:
        yield PipelineEvent(
            stage="error",
            payload={"message": f"Input exceeds maximum allowed limit ({limits.MAX_TEXT_CHARS} characters)."},
        )
        return

    # Check in-memory result cache
    norm_text = _normalize_text_for_cache(text)
    cache_key = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()

    if cache_key in _PIPELINE_CACHE:
        for stage_name, payload_data in _PIPELINE_CACHE[cache_key]:
            yield PipelineEvent(stage=stage_name, payload=payload_data)  # type: ignore[arg-type]
        return

    events_to_cache: list[tuple[str, dict]] = []

    try:
        # Stage 1: Extraction
        extraction_res = extract(text=text)
        evt_extracted = PipelineEvent(
            stage="extracted",
            payload={
                "extracted": extraction_res.extracted.model_dump(),
                "transcript": extraction_res.transcript,
            },
        )
        events_to_cache.append((evt_extracted.stage, evt_extracted.payload))
        yield evt_extracted

        # Stage 2: Offline Rule Checking
        flags = run_checker(extraction=extraction_res, text=text)

        # Compute preliminary verdict based solely on offline red flags
        prelim_score, prelim_verdict_str, _ = score_and_verdict(flags, [])
        prelim_exp = template_explanation(prelim_verdict_str, prelim_score, flags, [])
        preliminary_verdict = Verdict(
            verdict=prelim_verdict_str,  # type: ignore[arg-type]
            legitimacy_score=prelim_score,
            evidence_coverage="low",
            summary=prelim_exp["summary"],
            red_flags=flags,
            checks=[],
            positive_signs=[],
            next_steps=build_next_steps(prelim_verdict_str, flags),
            verify_links=[],
            extracted=extraction_res.extracted,
            preliminary=True,
        )
        evt_checker = PipelineEvent(
            stage="checker_done",
            payload=preliminary_verdict.model_dump(),
        )
        events_to_cache.append((evt_checker.stage, evt_checker.payload))
        yield evt_checker

        # Stage 3: Verification Checks
        # If any hard-fail scam indicator is present, skip web checks to save latency
        skip_web = any(f.id in HARD_CAP_IDS for f in flags)

        collected_checks = []
        for check in run_verifier(
            extraction=extraction_res,
            text=text,
            web_checks=web_checks,
            skip_web=skip_web,
        ):
            collected_checks.append(check)
            evt_check = PipelineEvent(
                stage="verifier_check",
                payload=check.model_dump(),
            )
            events_to_cache.append((evt_check.stage, evt_check.payload))
            yield evt_check

        # Stage 4: Synthesis & Final Verdict
        final_verdict = build_final(
            extraction_result=extraction_res,
            flags=flags,
            checks=collected_checks,
            text=text,
            web_checks=web_checks,
        )
        evt_final = PipelineEvent(
            stage="final",
            payload=final_verdict.model_dump(),
        )
        events_to_cache.append((evt_final.stage, evt_final.payload))

        # Store in LRU in-memory cache upon successful final synthesis
        if len(_PIPELINE_CACHE) >= _MAX_PIPELINE_CACHE_SIZE:
            _PIPELINE_CACHE.pop(next(iter(_PIPELINE_CACHE)))
        _PIPELINE_CACHE[cache_key] = events_to_cache

        yield evt_final

    except Exception:
        # Sanitized error message without leaking user input or internal traces
        yield PipelineEvent(
            stage="error",
            payload={"message": "An error occurred while analyzing the job offer. Please try again."},
        )


if __name__ == "__main__":
    content = sys.stdin.read()
    for event in run_pipeline(content):
        print(json.dumps({"stage": event.stage, "payload": event.payload}))
