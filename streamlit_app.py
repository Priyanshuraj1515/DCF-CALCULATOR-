import streamlit as st
from dcf_core import run_dcf_app

st.set_page_config(page_title="DCF + WACC Valuation Tool", layout="wide")
run_dcf_app()
