# multi_streamlined_roi_app.py

import streamlit as st

st.set_page_config(page_title="Multi-Path ROI Calculator", layout="centered")
st.title("🏥 Workforce ROI Intelligence Calculator")
st.markdown("**Choose Staffing Type to Begin**")

staffing_type = st.selectbox("Staffing Type", [
    "Physician (Locum)",
    "Nursing",
    "Allied Health"
])

# ---------------------------- LOCUMS ---------------------------- #
if staffing_type == "Physician (Locum)":
    st.header("📈 Locum ROI Inputs")
    beds = st.number_input("Beds Covered", value=20)
    revenue_per_bed = st.number_input("Revenue per Bed per Day ($)", value=7500)
    cost_per_bed = st.number_input("Cost per Bed per Day ($)", value=4000)
    referrals = st.number_input("Referrals per Bed", value=1.2)
    referral_value = st.number_input("Revenue per Referral ($)", value=900)

    locum_hourly = st.number_input("Locum Hourly Rate ($)", value=265)
    locum_hours = st.number_input("Hours per Shift", value=10)
    travel_cost = st.number_input("Travel/Housing per Day ($)", value=390)
    ftes = st.number_input("Locum FTEs", value=1)

    gross = beds * revenue_per_bed
    cost = beds * cost_per_bed
    referral_rev = beds * referrals * referral_value
    locum_total = (locum_hourly * locum_hours + travel_cost) * ftes

    net = gross + referral_rev - cost - locum_total

    st.subheader("💰 ROI Output")
    st.metric("Net ROI (Per Day)", f"${net:,.0f}")
    st.metric("Annualized ROI", f"${net * 365:,.0f}")

# ---------------------------- NURSING ---------------------------- #
elif staffing_type == "Nursing":
    st.header("🩺 Nursing ROI Inputs")
    beds = st.number_input("Beds Affected", value=20)
    rn_ratio = st.number_input("RN:Patient Ratio", value=1.0/4.0)
    traveler_cost = st.number_input("Traveler RN Hourly Cost ($)", value=95.0)
    los_baseline = st.number_input("Baseline LOS (days)", value=4.8)
    los_reduction_pct = st.slider("LOS Reduction %", 0, 100, 12)

    total_rns = int(beds * rn_ratio)
    los_saved = los_baseline * (los_reduction_pct / 100)
    bed_days_gained = beds * los_saved
    traveler_daily_cost = traveler_cost * 12 * total_rns  # assume 12 hr shifts

    value_of_bed_day = st.number_input("Avg Revenue per Bed Day ($)", value=2750)
    net_gain = bed_days_gained * value_of_bed_day - traveler_daily_cost

    st.subheader("💰 Cost Avoidance Output")
    st.metric("LOS-Driven Bed Days Gained", f"{bed_days_gained:,.1f}")
    st.metric("Net Savings (Per Day)", f"${net_gain:,.0f}")
    st.metric("Annualized Value", f"${net_gain * 365:,.0f}")

# ---------------------------- ALLIED ---------------------------- #
else:
    st.header("🧪 Allied ROI Inputs")
    st.markdown("_Estimate the impact of delays in diagnostics, rehab, etc._")
    delayed_procs = st.number_input("Delayed Procedures/Day", value=8)
    avg_proc_revenue = st.number_input("Avg Revenue per Procedure ($)", value=3200)
    per_diem_cost = st.number_input("Per Diem/Traveler Cost ($)", value=850)

    recovered_revenue = delayed_procs * avg_proc_revenue
    net_roi = recovered_revenue - per_diem_cost

    st.subheader("💰 ROI Output")
    st.metric("Recovered Revenue (Per Day)", f"${recovered_revenue:,.0f}")
    st.metric("Net ROI (Daily)", f"${net_roi:,.0f}")
    st.metric("Annualized ROI", f"${net_roi * 365:,.0f}")

st.markdown("---")
st.caption("🔄 Built for Physician, Nursing, and Allied ROI Modeling")

# --- Requirements.txt ---
# streamlit
# pandas

# --- README.md ---
# Multi-Path Healthcare ROI Calculator

## What This App Does
This Streamlit app models ROI for three healthcare staffing categories:
- Physician (Locum Tenens)
- Nursing (Traveler RNs)
- Allied Health (Diagnostics, Rehab, Therapists)

Each has tailored inputs and output metrics aligned with how ROI is measured in each field.

## How to Run
```bash
pip install -r requirements.txt
streamlit run multi_streamlined_roi_app.py
```

Built by [Your Company Name Here] to modernize staffing analytics for hospitals and agencies alike.
