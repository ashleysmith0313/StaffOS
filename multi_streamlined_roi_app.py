# multi_streamlined_roi_app.py

"""
This Streamlit app models ROI for three healthcare staffing categories:
1. Locum Tenens
2. Travel Nursing
3. Allied Health
"""

import streamlit as st

st.set_page_config(page_title="StaffOS ROI Platform", layout="wide")
st.title("📊 StaffOS Unified ROI Calculator")
st.markdown("**Smarter Staffing. All in One Place.**")

# Placeholder for service line selection and candidate mapping (future integration)
st.markdown("### Coming Soon: RadiusOS Mapping + ShiftSync ROI")

st.header("🏥 ROI Calculator: Select Your Staffing Type")

staffing_type = st.selectbox("Staffing Category", ["Locum Tenens", "Travel Nursing", "Allied Health"])

# Shared Inputs
st.subheader("🔧 Shift Setup")
total_beds = st.number_input("Total Beds in Unit", min_value=1, value=18)
occupancy_pct = st.slider("% of Beds Staffed Without Temp Staffing", 0, 100, 70)

# Locum Logic
if staffing_type == "Locum Tenens":
    st.subheader("🧑‍⚕️ Locum Inputs")
    hourly_rate = st.number_input("Hourly Rate ($)", value=265)
    hours_per_shift = st.number_input("Hours per Shift", value=10)
    travel_cost = st.number_input("Travel/Housing Cost per Day", value=390)
    locums_per_shift = st.number_input("Locums per Shift", value=1)
    utilization = st.slider("% Locum Utilization (Additional Coverage)", 0, 100, 80)
    
    revenue_per_bed = st.number_input("Revenue per Bed per Day ($)", value=8000)
    cost_per_bed = st.number_input("Cost per Bed per Day ($)", value=4500)
    referral_revenue = st.number_input("Referral Revenue per Bed ($)", value=700)

    staffed_beds = total_beds * (occupancy_pct + utilization) / 100
    gross_revenue = staffed_beds * revenue_per_bed
    gross_referral = staffed_beds * referral_revenue
    operating_cost = staffed_beds * cost_per_bed

    total_locum_cost = (hourly_rate * hours_per_shift + travel_cost) * locums_per_shift
    annual_locum_cost = total_locum_cost * 365

    net_margin = gross_revenue + gross_referral - operating_cost - total_locum_cost
    annual_net_margin = net_margin * 365

    missed_beds = total_beds - staffed_beds
    missed_revenue = missed_beds * (revenue_per_bed + referral_revenue - cost_per_bed)
    annual_missed = missed_revenue * 365

    st.subheader("💰 Results")
    st.metric("Staffed Beds This Shift", int(staffed_beds))
    st.metric("Net Margin (After Locum Cost)", f"${net_margin:,.0f}")
    
    if utilization > 0:
        st.markdown(f"### 📈 **Annualized Impact with Locums**")
        st.success(f"**Net ROI: ${annual_net_margin:,.0f}**\n\nLocum Cost: ${annual_locum_cost:,.0f}")
    else:
        st.markdown(f"### 📉 **Annualized Missed Opportunity Without Locums**")
        st.markdown(f"<div style='background-color:#990000;color:white;padding:1rem;border-radius:8px;'>Annualized Net Loss: <strong>(${annual_missed:,.0f})</strong></div>", unsafe_allow_html=True)

# Add Travel Nursing and Allied logic later
if staffing_type != "Locum Tenens":
    st.info("Only Locum ROI is active. Other categories coming soon!")

# Footer
st.markdown("---")
st.caption("Built with ❤️ by StaffOS | All calculations are for demonstration purposes only.")
