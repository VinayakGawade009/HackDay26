"""Query and display available Gemma models via Gemini API."""

import os
import sys
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def get_api_key() -> str | None:
    """Fetch GEMINI_API_KEY from environment or Streamlit secrets."""
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


def main() -> None:
    api_key = get_api_key()
    if not api_key:
        print("GEMINI_API_KEY is not set. Please set it in .env or your environment variables.")
        sys.exit(0)

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        print("Checking available models for 'gemma' (case-insensitive)...")
        models = list(client.models.list())
        gemma_models = [
            m for m in models
            if "gemma" in (getattr(m, "name", "") or "").lower()
            or "gemma" in (getattr(m, "display_name", "") or "").lower()
        ]

        if not gemma_models:
            print("No models containing 'gemma' found. Available models:")
            for m in models:
                display = getattr(m, "display_name", "") or ""
                print(f" - {m.name} ({display})")
        else:
            print(f"Found {len(gemma_models)} matching Gemma model(s):")
            for m in gemma_models:
                display = getattr(m, "display_name", "") or ""
                print(f" - {m.name} ({display})")

    except Exception as err:
        print(f"Failed to query models from Gemini API: {err}")


if __name__ == "__main__":
    main()
