"""
Streamlit App: StaffOS ROI Calculator
Filename: multi_streamlined_roi_app.py

This version includes:
- StaffOS logo display from /assets/
- Referral revenue logic (Cardiology, GI, Imaging, Surgery)
- Locum toggle with hourly or daily cost mode
- Staffed vs Unstaffed bed revenue modeling
- Annualized net impact display
"""

import streamlit as st
from PIL import Image
import os

# Load and display logo
logo_path = os.path.join("assets", "staffos_logo.png")
if os.path.exists(logo_path):
    logo = Image.open(logo_path)
    st.image(logo, width=200)
else:
    st.warning("Logo not found. Please add 'staffos_logo.png' in /assets/")

# Title
st.title("StaffOS ROI Calculator")

st.markdown("### Use Locums?")
use_locums = st.checkbox("Enable Locum Staffing", value=True)

# Locum rate input type
rate_type = st.radio("Select Locum Cost Type", ["Hourly Rate", "Daily Rate"])

if rate_type == "Hourly Rate":
    locum_hourly_rate = st.number_input("Hourly Rate ($)", value=265)
    hours_per_shift = st.number_input("Hours per Shift", value=12)
    locum_cost_per_day = locum_hourly_rate * hours_per_shift
else:
    locum_cost_per_day = st.number_input("Daily Rate ($)", value=3000)

# Travel & Housing Costs
travel_cost = st.number_input("Travel + Housing per Day ($)", value=390)

# Total locum cost
total_locum_cost = locum_cost_per_day + travel_cost

# Referral Revenue Inputs
st.markdown("### Referral Revenue Breakdown (Per Day)")
col1, col2 = st.columns(2)
with col1:
    cardiology_referrals = st.slider("Cardiology Referrals", 0, 5, 1)
    gi_referrals = st.slider("GI Referrals", 0, 5, 1)
with col2:
    imaging_referrals = st.slider("Imaging Referrals", 0, 5, 1)
    surgery_referrals = st.slider("Surgical Referrals", 0, 5, 1)

# Average reimbursement
referral_revenue = (
    cardiology_referrals * 500 +
    gi_referrals * 1250 +
    imaging_referrals * 900 +
    surgery_referrals * 3000
)

st.markdown(f"**Total Referral Revenue per Day: ${referral_revenue:,.2f}**")

# Bed revenue logic
st.markdown("### Bed Revenue & Costs")
beds_staffed = st.number_input("Beds Staffed", value=18)
avg_revenue_per_bed = st.number_input("Avg Revenue per Bed ($)", value=6000)
avg_cost_per_bed = st.number_input("Avg Cost per Bed ($)", value=4000)

gross_revenue = beds_staffed * avg_revenue_per_bed
total_costs = beds_staffed * avg_cost_per_bed

if use_locums:
    net_margin = gross_revenue + referral_revenue - total_costs - total_locum_cost
else:
    net_margin = gross_revenue + referral_revenue - total_costs

# Annualized Impact
annualized_margin = net_margin * 365
highlight_color = "green" if net_margin >= 0 else "red"
formatted_margin = f"${annualized_margin:,.2f}" if net_margin >= 0 else f"(${abs(annualized_margin):,.2f})"

st.markdown(f"### **Net Impact (Annualized)**")
st.markdown(f"<h3 style='color:{highlight_color}'>{formatted_margin}</h3>", unsafe_allow_html=True)
