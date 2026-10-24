"""Minimal smoke-test Streamlit entrypoint for SahiCheck."""

import streamlit as st
from llm import ask_gemma, LLMError

st.title("SahiCheck")

user_text = st.text_area("Enter job offer text to test:", height=150)

if st.button("Test model"):
    if not user_text.strip():
        st.warning("Please enter some text to test.")
    else:
        try:
            with st.spinner("Calling model..."):
                reply = ask_gemma(prompt=user_text.strip())
            st.success("Model response:")
            st.write(reply)
        except LLMError as err:
            st.error(str(err))
