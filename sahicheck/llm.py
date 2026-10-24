"""LLM interface for querying Gemma via the google-genai SDK."""

import hashlib
import os
import time
from typing import Any
from dotenv import load_dotenv

import limits

# Load environment variables from .env if present
load_dotenv()


class LLMError(Exception):
    """Raised on LLM failure with a user-safe message, never leaking prompt content."""
    pass


# In-memory cache for repeated identical queries: hash(model, prompt, image, json_mode) -> response
_CACHE: dict[str, str] = {}
_MAX_CACHE_ENTRIES = 128


def _get_api_key() -> str | None:
    """Read GEMINI_API_KEY from environment or Streamlit secrets as fallback."""
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            val = str(st.secrets["GEMINI_API_KEY"]).strip()
            if val:
                return val
    except Exception:
        pass
    return None


def _is_retryable(error: Exception) -> bool:
    """Check if error is transient rate-limit (429) or server error (5xx)."""
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code is not None:
        try:
            status = int(code)
            return status == 429 or status >= 500
        except (ValueError, TypeError):
            pass
    err_str = str(error).lower()
    return any(marker in err_str for marker in ("429", "resourceexhausted", "500", "503", "unavailable"))


def _make_cache_key(model: str, prompt: str, image_bytes: bytes | None, json_mode: bool) -> str:
    """Compute deterministic SHA-256 hash for cache keying."""
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(prompt.encode("utf-8"))
    hasher.update(b"json" if json_mode else b"text")
    if image_bytes:
        hasher.update(image_bytes)
    return hasher.hexdigest()


def ask_gemma(
    prompt: str,
    image_bytes: bytes | None = None,
    image_mime: str = "image/png",
    json_mode: bool = False,
) -> str:
    """Query Gemma model via google-genai SDK with caching, retry logic, and error sanitization."""
    # Model name from GEMMA_MODEL env var.
    # NOTE: Default "gemma-4-31b-it" is UNVERIFIED and must be confirmed with check_models.py.
    model_name = os.environ.get("GEMMA_MODEL", "gemma-4-31b-it").strip()

    # Check in-memory cache to return instant response for duplicate calls
    cache_key = _make_cache_key(model_name, prompt, image_bytes, json_mode)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    api_key = _get_api_key()
    if not api_key:
        raise LLMError("API key not configured. Set GEMINI_API_KEY in .env or Streamlit secrets.")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise LLMError("google-genai library is not installed.")

    client = genai.Client(api_key=api_key)

    # Build prompt and optional image attachment
    contents: list[Any] = []
    if image_bytes is not None:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))

    actual_prompt = prompt
    if json_mode:
        actual_prompt = f"{prompt}\n\nIMPORTANT: Output valid JSON only, without markdown fences or other text."
    contents.append(actual_prompt)

    # Configure timeout (HttpOptions expects milliseconds) and response format
    timeout_ms = int(limits.LLM_TIMEOUT_S * 1000)
    config_params: dict[str, Any] = {
        "http_options": types.HttpOptions(timeout=timeout_ms),
    }
    if json_mode:
        config_params["response_mime_type"] = "application/json"

    config = types.GenerateContentConfig(**config_params)

    # Primary model from GEMMA_MODEL env var.
    # NOTE: Default "gemma-4-31b-it" is UNVERIFIED. If it encounters a 500 server error,
    # we automatically fall back to verified available "gemma-4-26b-a4b-it".
    primary_model = os.environ.get("GEMMA_MODEL", "gemma-4-31b-it").strip()
    candidate_models = [primary_model]
    if primary_model != "gemma-4-26b-a4b-it":
        candidate_models.append("gemma-4-26b-a4b-it")

    # Retry loop with backoff for 429 and 5xx errors across candidate models
    for m_name in candidate_models:
        for attempt in range(limits.LLM_MAX_RETRIES + 1):
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=contents,
                    config=config,
                )
                text_out = response.text or ""

                # Store in in-memory cache
                if len(_CACHE) >= _MAX_CACHE_ENTRIES:
                    _CACHE.pop(next(iter(_CACHE)))
                _CACHE[cache_key] = text_out
                return text_out

            except Exception as exc:
                # Fallback if model rejects application/json response_mime_type
                if json_mode and "mime_type" in str(exc).lower():
                    try:
                        fallback_config = types.GenerateContentConfig(
                            http_options=types.HttpOptions(timeout=timeout_ms)
                        )
                        fallback_resp = client.models.generate_content(
                            model=m_name,
                            contents=contents,
                            config=fallback_config,
                        )
                        text_out = fallback_resp.text or ""
                        _CACHE[cache_key] = text_out
                        return text_out
                    except Exception as inner_exc:
                        exc = inner_exc

                # If server error (500) and we have another candidate model, break to next candidate
                if getattr(exc, "code", None) == 500 or "500" in str(exc):
                    break

                if attempt < limits.LLM_MAX_RETRIES and _is_retryable(error=exc):
                    time.sleep(limits.LLM_BACKOFF_S * (attempt + 1))
                    continue
                break

    # Sanitized error message without leaking sensitive user input or content
    raise LLMError("AI model service is currently unavailable or encountered an error. Please try again.")
