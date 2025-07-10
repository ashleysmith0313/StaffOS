
# multi_streamlined_roi_app.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Shift-Based Locum ROI Calculator", layout="centered")
st.title("🏥 Shift-Based Locum Coverage ROI Calculator")
st.markdown("**Powered by StaffOS**")

# --- Check for uploaded hospital data ---
hospital_data = st.session_state.get('hospital_data', None)

# --- Service Line Selection ---
default_service_line = hospital_data['Service Line'] if hospital_data else 'Med-Surg'
service_dict = {
    'ICU (Medical/Surgical)': {'revenue_per_bed': 8000.0, 'cost_per_bed': 4500.0, 'revenue_per_referral': 700.0},
    'ICU (Neuro/Trauma)': {'revenue_per_bed': 10000.0, 'cost_per_bed': 6000.0, 'revenue_per_referral': 750.0},
    'Med-Surg': {'revenue_per_bed': 2750.0, 'cost_per_bed': 1800.0, 'revenue_per_referral': 900.0},
    'Telemetry': {'revenue_per_bed': 3200.0, 'cost_per_bed': 2200.0, 'revenue_per_referral': 750.0},
    'Step-Down Unit': {'revenue_per_bed': 3500.0, 'cost_per_bed': 2500.0, 'revenue_per_referral': 750.0},
    'Rehab Unit': {'revenue_per_bed': 1500.0, 'cost_per_bed': 1000.0, 'revenue_per_referral': 583.33},
    'Cardiology (Inpatient)': {'revenue_per_bed': 5000.0, 'cost_per_bed': 3000.0, 'revenue_per_referral': 750.0},
    'Gastroenterology (Inpatient)': {'revenue_per_bed': 4200.0, 'cost_per_bed': 2800.0, 'revenue_per_referral': 1300.0},
    'Pulmonology (Inpatient)': {'revenue_per_bed': 4600.0, 'cost_per_bed': 3000.0, 'revenue_per_referral': 850.0},
    'Nephrology (Inpatient)': {'revenue_per_bed': 4000.0, 'cost_per_bed': 2600.0, 'revenue_per_referral': 850.0}
}

service_line = st.selectbox("Select Service Line", list(service_dict.keys()), index=list(service_dict.keys()).index(default_service_line))
unit_rev = hospital_data['Revenue per Bed'] if hospital_data else service_dict[service_line]['revenue_per_bed']
unit_cost = hospital_data['Cost per Bed'] if hospital_data else service_dict[service_line]['cost_per_bed']
revenue_per_referral = hospital_data['Revenue per Referral'] if hospital_data else service_dict[service_line]['revenue_per_referral']

# --- Editable Inputs ---
st.header("🔧 Shift Details")
default_beds = int(hospital_data['Total Beds']) if hospital_data else 18
total_beds = st.number_input("Total Beds in Unit", min_value=1, value=default_beds)
occupancy_pct = st.slider("Current Staffed Bed Percentage (%)", 0, 100, 75)
locum_toggle = st.checkbox("Use Locums?")
locum_count = st.number_input("Locums per Shift", min_value=0, value=1) if locum_toggle else 0
locum_coverage_pct = st.slider("Locum Utilization (%)", 0, 100, 80) if locum_toggle else 0

unit_rev = st.number_input("Average Revenue per Bed/Admit ($)", min_value=0, value=int(unit_rev))
unit_cost = st.number_input("Average Cost per Bed/Admit ($)", min_value=0, value=int(unit_cost))

# --- Referral Revenue Toggle ---
referral_toggle = st.checkbox("Include Referral Revenue?")
referral_revenue = 0
if referral_toggle:
    st.subheader("Referral Revenue (Downstream)")
    referrals_per_bed_default = hospital_data['Referrals per Bed'] if hospital_data else 1.2
    referrals_per_bed = st.number_input("Avg Referrals per Bed/Admission", min_value=0.0, value=referrals_per_bed_default)
    revenue_per_referral = st.number_input("Revenue per Referral ($)", min_value=0, value=int(revenue_per_referral))
    ref_total = total_beds * referrals_per_bed * (occupancy_pct + (locum_coverage_pct if locum_toggle else 0)) / 100
    referral_revenue = ref_total * revenue_per_referral
else:
    referrals_per_bed = 0

# --- Locum Cost Inputs ---
st.subheader("Locum Staffing Cost")
rate_type = st.radio("Rate Type", ["Hourly", "Daily"])
if rate_type == "Hourly":
    locum_hrly = st.number_input("Locum Hourly Rate ($)", min_value=0, value=265)
    locum_hrs = st.number_input("Hours per Shift", min_value=1, max_value=24, value=10)
    locum_cost_per = locum_hrly * locum_hrs
else:
    locum_cost_per = st.number_input("Locum Daily Rate ($)", min_value=0, value=2500)

locum_travel = st.number_input("Travel/Housing Cost per Day ($)", min_value=0, value=390)
locum_cost_total = (locum_cost_per + locum_travel) * locum_count if locum_toggle else 0
annualized_locum_cost = locum_cost_total * 365

# --- Financial Calculations ---
staffed_pct = occupancy_pct + (locum_coverage_pct if locum_toggle else 0)
beds_covered = int(total_beds * (staffed_pct / 100))
gross_rev = beds_covered * unit_rev
operating_cost = beds_covered * unit_cost
net_before_locum = gross_rev + referral_revenue - operating_cost
net_after_locum = net_before_locum - locum_cost_total
annualized_net = net_after_locum * 365
annualized_missed = (total_beds * (1 - staffed_pct / 100)) * (unit_rev + referrals_per_bed * revenue_per_referral - unit_cost) * 365

# --- Output Summary ---
st.header("📊 Shift Financial Summary")
st.metric("Beds Staffed This Shift", beds_covered)
st.metric("Unstaffed Beds", total_beds - beds_covered)
st.metric("Gross Revenue", f"${gross_rev:,.0f}")
st.metric("Operating Cost", f"${operating_cost:,.0f}")
st.metric("Referral Revenue", f"${referral_revenue:,.0f}")
st.metric("Net Before Locum", f"${net_before_locum:,.0f}")
st.metric("Locum Total Cost", f"${locum_cost_total:,.0f}")
st.metric("🔥 Net After Locum", f"${net_after_locum:,.0f}")

if locum_toggle:
    st.markdown("""
    ### 🧮 **Annual Impact**
    <div style='background-color:#d4f4dd;padding:1rem;border-radius:8px;'>
    <strong>Annualized ROI (With Locum): ${annualized_net:,.0f}</strong><br>
    <em>Annualized Locum Cost: ${annualized_locum_cost:,.0f}</em>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    ### 🧮 **Annual Missed Opportunity**
    <div style='background-color:#800000;padding:1rem;border-radius:8px;color:white;'>
    <strong>Annualized Net Loss: (${annualized_missed:,.0f})</strong>
    </div>
    """, unsafe_allow_html=True)
