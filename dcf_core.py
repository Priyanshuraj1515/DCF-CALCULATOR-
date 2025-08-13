
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO
from zipfile import ZipFile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ---------------------------
# Helper functions
# ---------------------------

def fetch_financial_data(ticker):
    stock = yf.Ticker(ticker)
    try:
        cashflow = stock.cashflow.loc['Total Cash From Operating Activities']
        capex = stock.cashflow.loc['Capital Expenditures']
        fcf = cashflow + capex  # Capex is negative in Yahoo data
        return fcf
    except Exception:
        return None

def calculate_wacc(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    # Cost of equity using CAPM
    try:
        risk_free_rate = yf.Ticker("^TNX").history(period="1d")['Close'][-1] / 100
    except:
        risk_free_rate = 0.04
    beta = info.get("beta", 1)
    market_return = 0.08
    cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)

    # Cost of debt
    total_debt = info.get("totalDebt", 0) or 0
    interest_expense = info.get("interestExpense", 0) or 0
    if total_debt > 0 and interest_expense != 0:
        cost_of_debt = abs(interest_expense) / total_debt
    else:
        cost_of_debt = 0.03

    tax_rate = info.get("effectiveTaxRate", 0.21) or 0.21

    market_cap = info.get("marketCap", 0) or 0
    equity_value = market_cap
    debt_value = total_debt

    if equity_value + debt_value == 0:
        return None

    wacc = (equity_value / (equity_value + debt_value)) * cost_of_equity +            (debt_value / (equity_value + debt_value)) * cost_of_debt * (1 - tax_rate)

    return {
        "wacc": wacc,
        "cost_of_equity": cost_of_equity,
        "cost_of_debt": cost_of_debt,
        "risk_free_rate": risk_free_rate,
        "beta": beta,
        "market_return": market_return,
        "tax_rate": tax_rate
    }

def project_fcf_multistage(fcf_values, stage1_growth, stage1_years, stage2_growth, stage2_years):
    last_fcf = fcf_values.iloc[0]
    projections = []
    for _ in range(stage1_years):
        last_fcf *= (1 + stage1_growth)
        projections.append(last_fcf)
    for _ in range(stage2_years):
        last_fcf *= (1 + stage2_growth)
        projections.append(last_fcf)
    return projections

def calculate_dcf(projections, discount_rate, terminal_growth):
    discounted = [fcf / ((1 + discount_rate) ** (i+1)) for i, fcf in enumerate(projections)]
    terminal_value = projections[-1] * (1 + terminal_growth) / (discount_rate - terminal_growth)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** len(projections))
    return sum(discounted) + discounted_terminal

def generate_pdf_report(ticker, fair_value, wacc_data, projections, buyback_rate):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, f"DCF + WACC Valuation Report: {ticker}")
    c.setFont("Helvetica", 12)
    c.drawString(50, 730, f"Fair Value per Share: ${fair_value:.2f}")
    c.drawString(50, 710, f"WACC: {wacc_data['wacc']*100:.2f}%")
    c.drawString(50, 690, f"Cost of Equity: {wacc_data['cost_of_equity']*100:.2f}%")
    c.drawString(50, 670, f"Cost of Debt: {wacc_data['cost_of_debt']*100:.2f}%")
    c.drawString(50, 650, f"Risk-Free Rate: {wacc_data['risk_free_rate']*100:.2f}%")
    c.drawString(50, 630, f"Beta: {wacc_data['beta']:.2f}")
    c.drawString(50, 610, f"Market Return: {wacc_data['market_return']*100:.2f}%")
    c.drawString(50, 590, f"Tax Rate: {wacc_data['tax_rate']*100:.2f}%")
    c.drawString(50, 570, f"Share Buyback Rate: {buyback_rate*100:.2f}% per year")
    c.drawString(50, 550, "Projected Free Cash Flows:")
    y_pos = 530
    for year, fcf in enumerate(projections, start=1):
        c.drawString(60, y_pos, f"Year {year}: ${fcf:,.0f}")
        y_pos -= 20
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ---------------------------
# Main Streamlit App
# ---------------------------

def run_dcf_app():
    st.title("DCF + WACC Valuation Tool")

    tab1, tab2, tab3 = st.tabs(["DCF Calculator", "Batch Reports", "WACC Helper"])

    # -------------------
    # Tab 1: DCF Calculator
    # -------------------
    with tab1:
        ticker = st.text_input("Enter Stock Ticker:", value="AAPL").upper()
        if "stored_wacc" not in st.session_state:
            st.session_state.stored_wacc = None

        if st.button("Fill from WACC Helper") and st.session_state.stored_wacc:
            discount_rate = st.session_state.stored_wacc["wacc"]
        else:
            discount_rate = st.number_input("Discount Rate (WACC) decimal:", value=0.08)

        stage1_growth = st.number_input("Stage 1 Growth Rate (decimal):", value=0.05)
        stage1_years = st.number_input("Stage 1 Years:", value=5, step=1)
        stage2_growth = st.number_input("Stage 2 Growth Rate (decimal):", value=0.03)
        stage2_years = st.number_input("Stage 2 Years:", value=5, step=1)
        terminal_growth = st.number_input("Terminal Growth (decimal):", value=0.02)
        buyback_rate = st.number_input("Annual Share Buyback Rate (decimal):", value=0.0)

        if st.button("Run Valuation"):
            fcf_values = fetch_financial_data(ticker)
            if fcf_values is None:
                st.error("Could not fetch financial data.")
                return

            projections = project_fcf_multistage(fcf_values, stage1_growth, stage1_years, stage2_growth, stage2_years)
            wacc_data = st.session_state.stored_wacc or calculate_wacc(ticker)
            if wacc_data is None:
                st.error("Could not calculate WACC.")
                return

            total_value = calculate_dcf(projections, discount_rate, terminal_growth)
            stock_info = yf.Ticker(ticker).info
            shares_outstanding = stock_info.get("sharesOutstanding", 1)

            # Adjust for buybacks
            adjusted_shares = shares_outstanding * ((1 - buyback_rate) ** (stage1_years + stage2_years))
            fair_value_per_share = total_value / adjusted_shares

            st.subheader(f"Fair Value per Share: ${fair_value_per_share:.2f}")
            st.write("WACC Breakdown:", wacc_data)

            pdf_buffer = generate_pdf_report(ticker, fair_value_per_share, wacc_data, projections, buyback_rate)
            st.download_button("Download PDF Report", pdf_buffer, file_name=f"{ticker}_dcf_report.pdf", mime="application/pdf")

    # -------------------
    # Tab 2: Batch Reports
    # -------------------
    with tab2:
        tickers_input = st.text_area("Enter tickers separated by commas:", value="AAPL,MSFT,GOOG")
        if st.button("Run Batch Reports"):
            tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, "w") as zf:
                for t in tickers:
                    fcf_values = fetch_financial_data(t)
                    if fcf_values is None:
                        continue
                    projections = project_fcf_multistage(fcf_values, 0.05, 5, 0.03, 5)
                    wacc_data = calculate_wacc(t) or {"wacc":0.08,"cost_of_equity":0,"cost_of_debt":0,"risk_free_rate":0,"beta":0,"market_return":0,"tax_rate":0}
                    total_value = calculate_dcf(projections, wacc_data["wacc"], 0.02)
                    stock_info = yf.Ticker(t).info
                    shares_outstanding = stock_info.get("sharesOutstanding", 1)
                    fair_value_per_share = total_value / shares_outstanding
                    pdf_buffer = generate_pdf_report(t, fair_value_per_share, wacc_data, projections, 0.0)
                    zf.writestr(f"{t}_dcf_report.pdf", pdf_buffer.read())
            zip_buffer.seek(0)
            st.download_button("Download ZIP of Reports", zip_buffer, file_name="batch_dcf_reports.zip", mime="application/zip")

    # -------------------
    # Tab 3: WACC Helper
    # -------------------
    with tab3:
        ticker_wacc = st.text_input("Enter Ticker for WACC:", value="AAPL").upper()
        if st.button("Calculate WACC") or True:  # auto-run
            wacc_data = calculate_wacc(ticker_wacc)
            if wacc_data:
                st.session_state.stored_wacc = wacc_data
                st.subheader(f"WACC for {ticker_wacc}: {wacc_data['wacc']*100:.2f}%")
                st.write("Breakdown:", wacc_data)
            else:
                st.error("Could not calculate WACC.")
