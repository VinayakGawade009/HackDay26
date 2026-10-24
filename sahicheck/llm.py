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


# Module-level variable tracking the specific model that generated the last answer
last_model_used: str | None = None

# In-memory cache for repeated identical queries: hash(model, prompt, image, json_mode) -> response
_CACHE: dict[str, str] = {}
_MAX_CACHE_ENTRIES = 128


def get_last_model_used() -> str | None:
    """Return the name of the model that answered the most recent call."""
    return last_model_used


def _get_api_key() -> str | None:
    """Read GEMINI_API_KEY from environment or Streamlit secrets as fallback.
    
    Never logs or prints the key.
    """
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


def _get_model_name() -> str:
    """Read GEMMA_MODEL from environment or Streamlit secrets with default fallback."""
    model = os.environ.get("GEMMA_MODEL")
    if model and model.strip():
        return model.strip()
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMMA_MODEL" in st.secrets:
            val = str(st.secrets["GEMMA_MODEL"]).strip()
            if val:
                return val
    except Exception:
        pass
    return "gemma-4-31b-it"


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
    global last_model_used

    primary_model = _get_model_name()

    # Check in-memory cache to return instant response for duplicate calls
    cache_key = _make_cache_key(primary_model, prompt, image_bytes, json_mode)
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

    # Primary model with automatic fallback to gemma-4-26b-a4b-it if primary encounters 500 error
    candidate_models = [primary_model]
    if primary_model != "gemma-4-26b-a4b-it":
        candidate_models.append("gemma-4-26b-a4b-it")

    # Retry loop with exponential backoff for 429 and 5xx errors (max 3 tries, wait under 20s)
    # backoffs: 2s, 4s, 8s -> total 14s < 20s
    max_retries = 3
    for m_name in candidate_models:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=contents,
                    config=config,
                )
                text_out = response.text or ""
                last_model_used = m_name

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
                        last_model_used = m_name
                        _CACHE[cache_key] = text_out
                        return text_out
                    except Exception as inner_exc:
                        exc = inner_exc

                # If server error (500) and an alternate model is available, move to fallback
                if (getattr(exc, "code", None) == 500 or "500" in str(exc)) and len(candidate_models) > 1 and m_name == candidate_models[0]:
                    break

                if attempt < max_retries - 1 and _is_retryable(error=exc):
                    backoff = min(limits.LLM_BACKOFF_S * (2 ** attempt), 8)
                    time.sleep(backoff)
                    continue
                break

    # Sanitized error message without leaking sensitive user input or content
    raise LLMError("AI model service is currently unavailable or encountered an error. Please try again.")
