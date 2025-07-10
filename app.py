
import streamlit as st
from PIL import Image
import os

# Load and display logo
logo_path = os.path.join("assets", "staffos_logo.png")
logo = Image.open(logo_path)
st.image(logo, width=200)

st.markdown("# StaffOS ROI Calculator")
st.markdown("### The smarter way to prove your staffing impact")

# Layout: Occupancy and Locum Toggles
st.markdown("## 🏥 Hospital Bed Utilization")
col1, col2, col3 = st.columns(3)

with col1:
    occupancy_rate = st.slider("Bed Occupancy %", min_value=50, max_value=100, value=85, step=5)
with col2:
    use_locums = st.toggle("Use Locums?", value=True)
with col3:
    locum_utilization = st.slider("Locum Utilization %", min_value=0, max_value=100, value=100, step=10)

# Locum inputs
if use_locums:
    st.markdown("### 🧑‍⚕️ Locum Staffing Details")
    col4, col5 = st.columns(2)
    with col4:
        locum_count = st.number_input("Locums Per Shift", min_value=1, max_value=10, value=2)
    with col5:
        hourly_rate = st.number_input("Hourly Locum Rate ($)", min_value=100, max_value=400, value=265)
    travel_cost = st.number_input("Daily Travel Cost ($)", min_value=0, max_value=1000, value=390)

# Constants
beds_per_locum = 20  # default bed coverage per locum
avg_revenue_per_bed = 4000  # blended ICU/MedSurg estimate
avg_cost_per_bed = 2500
hours_per_day = 12

# Calculations
staffed_beds = int((occupancy_rate / 100) * (locum_count * beds_per_locum if use_locums else 100))
daily_revenue = staffed_beds * avg_revenue_per_bed
daily_costs = staffed_beds * avg_cost_per_bed
locum_daily_total = (hourly_rate * hours_per_day + travel_cost) * locum_count * (locum_utilization / 100) if use_locums else 0
net_revenue = daily_revenue - daily_costs - locum_daily_total
annualized_net = net_revenue * 365
missed_beds = 100 - staffed_beds if staffed_beds < 100 else 0
missed_revenue = missed_beds * avg_revenue_per_bed
annual_missed_revenue = missed_revenue * 365

# Output summary area
st.markdown("---")
st.markdown("## 💸 ROI Summary")
col6, col7, col8 = st.columns(3)
col6.metric("Daily Gross Revenue", f"${daily_revenue:,.0f}")
col7.metric("Daily Net Revenue", f"${net_revenue:,.0f}", delta_color="inverse")
col8.metric("Annualized Net Revenue", f"${annualized_net:,.0f}")

if not use_locums:
    st.markdown(f"#### 🧾 Missed Annual Revenue: :red[(${annual_missed_revenue:,.0f})]")

# Footer
st.markdown("---")
st.caption("📊 All calculations are estimates based on average industry data. Built with ♥ by StaffOS.")
