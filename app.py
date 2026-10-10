import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Config ---
st.set_page_config(
    page_title="AlphaValuation - DCF Model",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AlphaValuation - DCF Model")
st.caption("เครื่องมือประเมินมูลค่าหุ้นด้วยวิธี Discounted Cash Flow (DCF) สไตล์ Alpha Spread")
st.divider()

# --- Sidebar Inputs ---
st.sidebar.header("🔍 ตั้งค่าและดึงข้อมูลหุ้น")
ticker_symbol = st.sidebar.text_input("สัญลักษณ์หุ้น (Ticker)", value="AAPL").upper().strip()

# Default Values
def_price = 175.0
def_fcf = 100000.0
def_shares = 15500.0

if st.sidebar.button("📥 ดึงข้อมูลราคาและงบการเงิน"):
    try:
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        cashflow = stock.cashflow

        live_price = info.get('currentPrice') or info.get('regularMarketPrice')
        live_shares = info.get('sharesOutstanding')
        
        live_fcf = None
        if not cashflow.empty:
            if 'Free Cash Flow' in cashflow.index:
                live_fcf = cashflow.loc['Free Cash Flow'].iloc[0]
            elif 'Operating Cash Flow' in cashflow.index and 'Capital Expenditures' in cashflow.index:
                live_fcf = cashflow.loc['Operating Cash Flow'].iloc[0] + cashflow.loc['Capital Expenditures'].iloc[0]

        if live_price: def_price = float(live_price)
        if live_shares: def_shares = float(live_shares) / 1e6
        if live_fcf: def_fcf = float(live_fcf) / 1e6
        
        st.sidebar.success(f"ดึงข้อมูลสำเร็จสำหรับ {ticker_symbol}")
    except Exception as e:
        st.sidebar.error(f"เกิดข้อผิดพลาด: {e}")

st.sidebar.subheader("1. ข้อมูลการเงินพื้นฐาน")
current_price = st.sidebar.number_input("ราคาหุ้นปัจจุบัน ($)", value=def_price, step=1.0)
fcf_base = st.sidebar.number_input("FCF ล่าสุด ($ Millions)", value=def_fcf, step=500.0)
shares_outstanding = st.sidebar.number_input("จำนวนหุ้นทั้งหมด (Millions)", value=def_shares, step=100.0)

st.sidebar.subheader("2. สมมติฐานการเติบโต")
growth_stage1 = st.sidebar.slider("เติบโต ปี 1-5 (%)", 0.0, 40.0, 10.0) / 100
growth_stage2 = st.sidebar.slider("เติบโต ปี 6-10 (%)", 0.0, 25.0, 6.0) / 100
terminal_growth = st.sidebar.slider("เติบโตถาวร Perpetual (%)", 0.0, 5.0, 2.5) / 100

st.sidebar.subheader("3. อัตราคิดลด (WACC)")
wacc = st.sidebar.slider("WACC / Discount Rate (%)", 5.0, 20.0, 8.5) / 100

# --- DCF Calculation Logic ---
def calculate_dcf(g1, g2, g_term, discount_rate, fcf, shares):
    years = list(range(1, 11))
    fcf_list = []
    pv_list = []
    curr_fcf = fcf

    for yr in years:
        rate = g1 if yr <= 5 else g2
        curr_fcf *= (1 + rate)
        discount_factor = (1 + discount_rate) ** yr
        pv = curr_fcf / discount_factor
        fcf_list.append(curr_fcf)
        pv_list.append(pv)

    term_val = (fcf_list[-1] * (1 + g_term)) / (discount_rate - g_term)
    pv_term_val = term_val / ((1 + discount_rate) ** 10)
    
    total_pv_fcf = sum(pv_list)
    equity_val = total_pv_fcf + pv_term_val
    intrinsic_val = equity_val / shares
    margin = ((intrinsic_val - current_price) / current_price) * 100

    return intrinsic_val, margin, fcf_list, pv_list, total_pv_fcf, pv_term_val, equity_val

# Calculate Values
intrinsic_val, margin, fcf_projections, pv_fcf, total_pv, pv_terminal, equity_val = calculate_dcf(
    growth_stage1, growth_stage2, terminal_growth, wacc, fcf_base, shares_outstanding
)

# --- Display Results ---
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("ราคาตลาดปัจจุบัน", f"${current_price:,.2f}")

with col2:
    st.metric("มูลค่าที่แท้จริง (Intrinsic Value)", f"${intrinsic_val:,.2f}")

with col3:
    val_type = "Undervalued" if margin > 0 else "Overvalued"
    st.metric("ผลการประเมินมูลค่า", f"{val_type} {abs(margin):.1f}%")

st.divider()

# --- Scenario Analysis ---
st.subheader("🎯 การวิเคราะห์สถานการณ์ (Scenario Analysis)")
s_col1, s_col2, s_col3 = st.columns(3)

bear_val, bear_margin, *_ = calculate_dcf(growth_stage1 * 0.7, growth_stage2 * 0.7, terminal_growth, wacc * 1.1, fcf_base, shares_outstanding)
bull_val, bull_margin, *_ = calculate_dcf(growth_stage1 * 1.3, growth_stage2 * 1.3, terminal_growth, wacc * 0.9, fcf_base, shares_outstanding)

with s_col1:
    st.warning(f"🐻 Bear Case: **${bear_val:,.2f}** ({'Undervalued' if bear_margin>0 else 'Overvalued'} {abs(bear_margin):.1f}%)")
with s_col2:
    st.info(f"📊 Base Case: **${intrinsic_val:,.2f}** ({'Undervalued' if margin>0 else 'Overvalued'} {abs(margin):.1f}%)")
with s_col3:
    st.success(f"🐂 Bull Case: **${bull_val:,.2f}** ({'Undervalued' if bull_margin>0 else 'Overvalued'} {abs(bull_margin):.1f}%)")

st.divider()

# --- Graph ---
st.subheader(f"📈 ประมาณการกระแสเงินสดล่วงหน้า 10 ปี ({ticker_symbol})")
df_years = [f"Year {i}" for i in range(1, 11)]

fig = go.Figure()
fig.add_trace(go.Bar(x=df_years, y=fcf_projections, name="Projected FCF ($M)", marker_color='#26a69a'))
fig.add_trace(go.Bar(x=df_years, y=pv_fcf, name="PV of FCF ($M)", marker_color='#29b6f6'))
fig.update_layout(barmode='group', template='plotly_dark', height=400)
st.plotly_chart(fig, use_container_width=True)

# Breakdown
st.subheader("🧩 โครงสร้างการประเมินมูลค่า (Valuation Breakdown)")
b1, b2, b3 = st.columns(3)
b1.metric("PV of 10-Year Cash Flows", f"${total_pv:,.2f} M")
b2.metric("PV of Terminal Value", f"${pv_terminal:,.2f} M")
b3.metric("Total Equity Value", f"${equity_val:,.2f} M")