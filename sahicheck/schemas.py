"""Pydantic v2 data models for SahiCheck."""

from typing import Literal
from pydantic import BaseModel, Field


class Flag(BaseModel):
    """Represents a suspicious indicator or red flag detected in a job offer."""

    id: str
    severity: Literal["low", "medium", "high"]
    evidence: str
    why_it_matters: str = ""


class Check(BaseModel):
    """Represents an individual deterministic or web verification check result."""

    id: str
    name: str
    tier: Literal["strong", "supporting", "weak"]
    status: Literal["passed", "failed", "unavailable"]
    detail: str
    source: Literal["offline", "web"]
    score_delta: int = 0


class VerifyLink(BaseModel):
    """Provides a safe verification hyperlink for manual cross-checking."""

    label: str
    url: str


class Extracted(BaseModel):
    """Structured entities extracted from job offer text or visual documents."""

    company: str = ""
    role: str = ""
    pay: str = ""
    channel: str = ""
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    upi_ids: list[str] = Field(default_factory=list)
    amounts: list[str] = Field(default_factory=list)
    unverified_fields: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Bundles extracted entities with raw transcript and detected visual cues."""

    extracted: Extracted
    transcript: str = ""
    visual_cues: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    """Final assessment containing legitimacy score, red flags, and next steps."""

    verdict: Literal["SAFE", "SUSPICIOUS", "SCAM"]
    legitimacy_score: int
    evidence_coverage: Literal["low", "medium", "high"]
    summary: str
    red_flags: list[Flag] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    positive_signs: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    verify_links: list[VerifyLink] = Field(default_factory=list)
    extracted: Extracted
    preliminary: bool = False


class PipelineEvent(BaseModel):
    """Represents an execution event emitted during the multi-stage pipeline."""

    stage: Literal["extracted", "checker_done", "verifier_check", "final", "error"]
    payload: dict = Field(default_factory=dict)
