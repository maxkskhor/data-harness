"""Streamlit demo: ask questions about an uploaded CSV.

    uv run streamlit run examples/streamlit_app.py

Needs an API key (OPENROUTER_API_KEY / ANTHROPIC_API_KEY / ...) and the [demo]
extra (`pip install "data-harness[demo]"`).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from data_harness import ask

load_dotenv()

st.set_page_config(page_title="data-harness", page_icon="📊")
st.title("data-harness")
st.caption("Ask questions about your data — controlled Python, not bash.")

uploaded = st.file_uploader("Upload a CSV", type=["csv"])
model = st.text_input("Model (optional, e.g. deepseek/deepseek-v4-flash)", value="")
question = st.text_input("Question", value="What are the key insights in this data?")

if uploaded is not None:
    df = pd.read_csv(uploaded)
    st.dataframe(df.head())

    if st.button("Ask") and question:
        with st.spinner("Running the agent…"):
            result = ask(df, question, model=model or None)

        if result.text:
            st.markdown(result.text)
        if result.value is not None and not isinstance(result.value, pd.DataFrame):
            st.metric("Answer", str(result.value))
        elif isinstance(result.value, pd.DataFrame):
            st.dataframe(result.value)
        for chart in result.charts:
            # pass bytes (not a path) so the image always renders
            st.image(chart.read_bytes(), caption=chart.title or "chart")

        st.caption(
            f"{result.turns} turns · "
            f"{result.usage.input_tokens + result.usage.output_tokens:,} tokens"
        )
