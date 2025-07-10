
# multi_streamlined_roi_app.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="StaffOS ROI Calculator", layout="wide")

# Centered and resized logo
st.markdown(
    """
    <div style='text-align: center;'>
        <img src='https://staffos.streamlit.app/assets/logo.png' alt='StaffOS Logo' width='300'/>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("🏥 Shift-Based Locum Coverage ROI Calculator")
st.markdown("**Powered by StaffOS**")

# Optional upload section for future live version
with st.expander("📁 Upload Hospital Data (Optional)", expanded=False):
    uploaded_file = st.file_uploader("Upload Excel or CSV", type=["csv", "xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith("xlsx") else pd.read_csv(uploaded_file)
        st.subheader("📋 Uploaded Hospital Data")
        st.dataframe(df)

# --- Role Logic ---
role = st.selectbox("Select Coverage Type", [
    "Daytime Hospitalist (Med-Surg only)",
    "Daytime Hospitalist (Med-Surg + ICU)",
    "Nocturnist (Admits + Cross-Cover)"
])

if role == "Daytime Hospitalist (Med-Surg only)":
    total_beds = 18
    unit_rev = 2750
    unit_cost = 1850
    referrals_per_bed = 1.2
elif role == "Daytime Hospitalist (Med-Surg + ICU)":
    total_beds = 22
    unit_rev = (2750 * 15 + 8000 * 7) / 22
    unit_cost = (1850 * 15 + 4500 * 7) / 22
    referrals_per_bed = (1.2 * 15 + 2.5 * 7) / 22
elif role == "Nocturnist (Admits + Cross-Cover)":
    total_beds = 12
    unit_rev = 3000
    unit_cost = 2000
    referrals_per_bed = 0.8

# --- Shift Details ---
st.header("🔧 Shift Details")
total_beds = st.number_input("Total Beds in Unit", min_value=1, value=total_beds)
occupancy_pct = st.slider("Current Staffed Bed Percentage (%)", 0, 100, 75)
locum_toggle = st.checkbox("Use Locums?")
locum_count = st.number_input("Locums per Shift", min_value=0, value=1) if locum_toggle else 0
locum_coverage_pct = st.slider("Locum Utilization (%)", 0, 100, 80) if locum_toggle else 0
unit_rev = st.number_input("Average Revenue per Bed/Admit ($)", min_value=0, value=int(unit_rev))
unit_cost = st.number_input("Average Cost per Bed/Admit ($)", min_value=0, value=int(unit_cost))

# --- Referral Revenue ---
st.subheader("Referral Revenue (Downstream)")
referrals_per_bed = st.number_input("Avg Referrals per Bed/Admission", min_value=0.0, value=referrals_per_bed)
revenue_per_referral = st.number_input("Revenue per Referral ($)", min_value=0, value=900)

ref_total = total_beds * referrals_per_bed * (occupancy_pct + (locum_coverage_pct if locum_toggle else 0)) / 100
st.write(f"📌 Estimated Total Referrals This Shift: **{ref_total:.1f}**")

st.markdown("Adjust the % distribution of referral types below. Total must equal 100%.")
col1, col2 = st.columns(2)
with col1:
    cardio_pct = st.slider("Cardiology (%)", 0, 100, 30)
    surgery_pct = st.slider("Surgery (%)", 0, 100, 25)
with col2:
    gi_pct = st.slider("GI (%)", 0, 100, 25)
    imaging_pct = st.slider("Imaging/Diagnostics (%)", 0, 100, 20)

total_pct = cardio_pct + gi_pct + surgery_pct + imaging_pct
if total_pct != 100:
    st.error("⚠️ Referral type percentages must total 100%. Adjust sliders.")
    st.stop()

cardio_rev = 500
gi_rev = 1200
surgery_rev = 3000
imaging_rev = 800

cardio_income = ref_total * (cardio_pct / 100) * cardio_rev
gi_income = ref_total * (gi_pct / 100) * gi_rev
surgery_income = ref_total * (surgery_pct / 100) * surgery_rev
imaging_income = ref_total * (imaging_pct / 100) * imaging_rev

referral_revenue = cardio_income + gi_income + surgery_income + imaging_income

# --- Locum Cost Options ---
st.subheader("Locum Staffing Cost")
rate_type = st.radio("Select Rate Type", ["Hourly", "Daily"])
if rate_type == "Hourly":
    locum_hrly = st.number_input("Hourly Rate ($)", min_value=0, value=265)
    locum_hrs = st.number_input("Hours per Shift", min_value=1, max_value=24, value=10)
    locum_base = locum_hrly * locum_hrs
else:
    locum_base = st.number_input("Daily Rate ($)", min_value=0, value=2650)

locum_travel = st.number_input("Travel/Housing Cost per Day ($)", min_value=0, value=390)
locum_cost_per = locum_base + locum_travel
locum_total = locum_cost_per * locum_count if locum_toggle else 0
annualized_locum_cost = locum_total * 365

# --- Financial Calculations ---
staffed_pct = occupancy_pct + (locum_coverage_pct if locum_toggle else 0)
beds_covered = int(total_beds * (staffed_pct / 100))
gross_rev = beds_covered * unit_rev
operating_cost = beds_covered * unit_cost
net_before_locum = gross_rev + referral_revenue - operating_cost
net_after_locum = net_before_locum - locum_total
annualized_net = net_after_locum * 365
annualized_missed = (total_beds * (1 - staffed_pct / 100)) * (unit_rev + referrals_per_bed * revenue_per_referral - unit_cost) * 365

# --- Output Summary ---
st.header("📊 Shift Financial Summary")
st.metric("Beds Staffed This Shift", beds_covered)
st.metric("Unstaffed Beds (Missed Opportunity)", total_beds - beds_covered)
st.metric("Gross Revenue from Staffed Beds", f"${gross_rev:,.0f}")
st.metric("Operating Cost for Staffed Beds", f"${operating_cost:,.0f}")
st.metric("Referral Revenue Generated", f"${referral_revenue:,.0f}")
st.metric("Net Margin Before Locum Cost", f"${net_before_locum:,.0f}")
st.metric("Locum Total Cost for Shift", f"${locum_total:,.0f}")
st.metric("🔥 Net Financial Impact (After Locum)", f"${net_after_locum:,.0f}")

if locum_toggle:
    st.markdown(f"""
    ### 🧮 **Estimated Annual Impact (365 Days)**
    <div style='background-color:#d4f4dd;padding:1rem;border-radius:8px;'>
    <strong>Annualized Net ROI (With Locum): ${annualized_net:,.0f}</strong><br>
    <em>Annualized Locum Cost: ${annualized_locum_cost:,.0f}</em>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    ### 🧮 **Estimated Annual Missed Opportunity (365 Days)**
    <div style='background-color:#800000;padding:1rem;border-radius:8px;color:white;'>
    <strong>Annualized Net Loss: (${annualized_missed:,.0f})</strong>
    </div>
    """, unsafe_allow_html=True)

if locum_toggle:
    if net_after_locum >= 0:
        st.success("✅ Positive ROI from locum coverage, including referral revenue.")
    else:
        st.warning("⚠️ Locum coverage reduces net margin, but protects top-line and referral throughput.")
