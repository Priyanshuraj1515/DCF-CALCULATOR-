
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import zipfile
import datetime

# Debug log helper
def log_debug(message):
    st.write(f"**[DEBUG]** {message}")

def fetch_financial_data(ticker):
    try:
        log_debug(f"Fetching financial data for {ticker}...")
        stock = yf.Ticker(ticker)
        
        cashflow_df = stock.cashflow
        if cashflow_df is None or cashflow_df.empty:
            log_debug("Annual cashflow empty, trying quarterly cashflow...")
            cashflow_df = stock.quarterly_cashflow

        if cashflow_df is None or cashflow_df.empty:
            log_debug("Both annual and quarterly cashflows are empty.")
            return None
        
        log_debug(f"Cashflow data available: {cashflow_df.index.tolist()}")
        
        if "Total Cash From Operating Activities" in cashflow_df.index:
            cfo = cashflow_df.loc["Total Cash From Operating Activities"]
        else:
            log_debug("'Total Cash From Operating Activities' not found.")
            return None

        if "Capital Expenditures" in cashflow_df.index:
            capex = cashflow_df.loc["Capital Expenditures"]
        else:
            log_debug("'Capital Expenditures' not found.")
            return None
        
        fcf = cfo + capex
        fcf = fcf.dropna().sort_index(ascending=False)
        log_debug(f"Free Cash Flow values fetched: {fcf.to_dict()}")

        return fcf.head(5)
    
    except Exception as e:
        log_debug(f"Error fetching financial data: {e}")
        return None

def run_dcf_app():
    st.title("DCF + WACC Valuation Tool")

    ticker = st.text_input("Enter Ticker Symbol (e.g., AAPL):")
    stage1_growth = st.number_input("Stage 1 Growth Rate (decimal):", value=0.05)
    stage1_years = st.number_input("Stage 1 Years:", value=5, step=1)
    stage2_growth = st.number_input("Stage 2 Growth Rate (decimal):", value=0.03)
    stage2_years = st.number_input("Stage 2 Years:", value=5, step=1)
    terminal_growth = st.number_input("Terminal Growth (decimal):", value=0.02)
    buyback_rate = st.number_input("Annual Share Buyback Rate (decimal):", value=0.0)
    discount_rate = st.number_input("Discount Rate / WACC (decimal):", value=0.08)

    if st.button("Run Valuation"):
        fcf_series = fetch_financial_data(ticker)
        if fcf_series is None or len(fcf_series) == 0:
            st.error("Could not fetch financial data. See debug logs above.")
            return
        
        avg_fcf = np.mean(fcf_series)
        st.write(f"Average FCF (last {len(fcf_series)} years): {avg_fcf:,.0f}")

        projections = []
        fcf = avg_fcf

        for _ in range(int(stage1_years)):
            fcf *= (1 + stage1_growth)
            projections.append(fcf)
        for _ in range(int(stage2_years)):
            fcf *= (1 + stage2_growth)
            projections.append(fcf)

        terminal_value = projections[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
        projections.append(terminal_value)

        discounted = [proj / ((1 + discount_rate) ** (i+1)) for i, proj in enumerate(projections)]
        total_value = sum(discounted)
        st.success(f"Estimated Fair Value: {total_value:,.0f}")

if __name__ == "__main__":
    run_dcf_app()
