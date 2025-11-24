import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
PROVIDERS_FILE = DATA_DIR / "providers.json"
SITES_FILE = DATA_DIR / "sites.json"
SHIFTS_FILE = DATA_DIR / "shifts.json"


# ---------- Data helpers ----------

def load_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_all_data():
    providers = load_json(PROVIDERS_FILE)
    sites = load_json(SITES_FILE)
    shifts = load_json(SHIFTS_FILE)
    return providers, sites, shifts


def get_site_name(site_id: int, sites: List[Dict[str, Any]]) -> str:
    for s in sites:
        if s["id"] == site_id:
            return s["name"]
    return "Unknown Site"


def get_provider_display(provider_id: Optional[int], providers: List[Dict[str, Any]]) -> str:
    if provider_id is None:
        return "Unassigned"
    for p in providers:
        if p["id"] == provider_id:
            # p["type"] is interpreted as role / service line
            return f"{p['name']} ({p['type']})"
    return "Unknown Provider"


# ---------- UI pages ----------

def page_dashboard(providers, sites, shifts):
    st.title("Provider Scheduling Dashboard")

    # Unfilled shifts
    unfilled = [s for s in shifts if s.get("provider_id") is None]
    assigned_provider_ids = {s["provider_id"] for s in shifts if s.get("provider_id") is not None}
    available_providers = [p for p in providers if p["id"] not in assigned_provider_ids]

    # Sites overview
    sites_overview = []
    for site in sites:
        site_shifts = [s for s in shifts if s["site_id"] == site["id"]]
        unfilled_count = sum(1 for s in site_shifts if s.get("provider_id") is None)
        sites_overview.append(
            {
                "Site": site["name"],
                "Total Shifts": len(site_shifts),
                "Unfilled Shifts": unfilled_count,
            }
        )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Unfilled Shifts")
        if not unfilled:
            st.info("All shifts are currently filled.")
        else:
            rows = []
            for s in unfilled:
                rows.append(
                    {
                        "Date": s["date"],
                        "Site": get_site_name(s["site_id"], sites),
                        "Start": s["start_time"],
                        "End": s["end_time"],
                    }
                )
            st.table(pd.DataFrame(rows))

    with col2:
        st.subheader("Available Providers")
        if not available_providers:
            st.warning("No providers are currently fully available.")
        else:
            rows = [
                {
                    "Name": p["name"],
                    "Role / Service Line": p["type"]
                }
                for p in available_providers
            ]
            st.table(pd.DataFrame(rows))

    st.subheader("Sites Overview")
    st.table(pd.DataFrame(sites_overview))


def page_providers(providers, sites):
    st.title("Providers")

    if not providers:
        st.warning("No providers found.")
        return

    df = pd.DataFrame(providers)
    df_display = df.rename(
        columns={
            "id": "ID",
            "name": "Name",
            "type": "Role / Service Line"
        }
    )
    st.dataframe(df_display[["ID", "Name", "Role / Service Line"]])


def page_sites(sites):
    st.title("Sites")

    if not sites:
        st.warning("No sites found.")
        return

    df = pd.DataFrame(sites).rename(columns={"id": "ID", "name": "Site Name"})
    st.dataframe(df)


def page_shifts(providers, sites, shifts):
    st.title("Shifts")

    # Display current shifts table
    if shifts:
        display_rows = []
        for s in shifts:
            display_rows.append(
                {
                    "ID": s["id"],
                    "Date": s["date"],
                    "Site": get_site_name(s["site_id"], sites),
                    "Start": s["start_time"],
                    "End": s["end_time"],
                    "Provider": get_provider_display(s.get("provider_id"), providers),
                }
            )
        st.subheader("Existing Shifts")
        st.dataframe(pd.DataFrame(display_rows))
    else:
        st.info("No shifts created yet.")

    st.markdown("---")

    # Create new shift
    st.subheader("Create New Shift")
    with st.form("create_shift_form"):
        col1, col2 = st.columns(2)
        with col1:
            site_choice = st.selectbox(
                "Site",
                options=sites,
                format_func=lambda s: s["name"] if isinstance(s, dict) else str(s),
            )
            date = st.date_input("Date")
        with col2:
            start_time = st.time_input("Start Time")
            end_time = st.time_input("End Time")

        provider_options = ["Unassigned"] + [f"{p['name']} ({p['type']})" for p in providers]
        provider_choice = st.selectbox("Assign Provider (optional)", provider_options)

        submitted = st.form_submit_button("Create Shift")

        if submitted:
            if not site_choice or not date or not start_time or not end_time:
                st.error("All shift fields except provider are required.")
            else:
                new_id = max([s["id"] for s in shifts], default=0) + 1
                provider_id = None
                if provider_choice != "Unassigned":
                    selected_provider = next(
                        p for p in providers if f"{p['name']} ({p['type']})" == provider_choice
                    )
                    provider_id = selected_provider["id"]

                new_shift = {
                    "id": new_id,
                    "site_id": site_choice["id"],
                    "provider_id": provider_id,
                    "date": date.isoformat(),
                    "start_time": start_time.strftime("%H:%M"),
                    "end_time": end_time.strftime("%H:%M"),
                }

                shifts.append(new_shift)
                save_json(SHIFTS_FILE, shifts)
                st.success(f"Shift {new_id} created.")
                st.experimental_rerun()

    st.markdown("---")

    # Edit / delete existing shift
    st.subheader("Edit or Delete Shift")

    if not shifts:
        st.info("No shifts available to edit.")
        return

    shift_options = {
        f"#{s['id']} – {s['date']} – {get_site_name(s['site_id'], sites)}": s
        for s in shifts
    }
    selected_label = st.selectbox("Select Shift", list(shift_options.keys()))
    selected_shift = shift_options[selected_label]

    with st.form("edit_shift_form"):
        col1, col2 = st.columns(2)
        with col1:
            edit_site = st.selectbox(
                "Site",
                options=sites,
                index=next(i for i, s in enumerate(sites) if s["id"] == selected_shift["site_id"]),
                format_func=lambda s: s["name"] if isinstance(s, dict) else str(s),
            )
            edit_date = st.date_input("Date", pd.to_datetime(selected_shift["date"]))
        with col2:
            edit_start_time = st.time_input(
                "Start Time",
                pd.to_datetime(selected_shift["start_time"], format="%H:%M").time()
            )
            edit_end_time = st.time_input(
                "End Time",
                pd.to_datetime(selected_shift["end_time"], format="%H:%M").time()
            )

        provider_options = ["Unassigned"] + [f"{p['name']} ({p['type']})" for p in providers]
        if selected_shift.get("provider_id") is None:
            default_idx = 0
        else:
            current_provider = next(
                (p for p in providers if p["id"] == selected_shift["provider_id"]),
                None,
            )
            label = "Unassigned"
            if current_provider:
                label = f"{current_provider['name']} ({current_provider['type']})"
            default_idx = provider_options.index(label)

        edit_provider_choice = st.selectbox(
            "Assign Provider (optional)",
            provider_options,
            index=default_idx,
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            save_btn = st.form_submit_button("Save Changes")
        with col_btn2:
            delete_btn = st.form_submit_button("Delete Shift")

        if save_btn:
            provider_id = None
            if edit_provider_choice != "Unassigned":
                selected_provider = next(
                    p for p in providers if f"{p['name']} ({p['type']})" == edit_provider_choice
                )
                provider_id = selected_provider["id"]

            for s in shifts:
                if s["id"] == selected_shift["id"]:
                    s["site_id"] = edit_site["id"]
                    s["date"] = edit_date.isoformat()
                    s["start_time"] = edit_start_time.strftime("%H:%M")
                    s["end_time"] = edit_end_time.strftime("%H:%M")
                    s["provider_id"] = provider_id

            save_json(SHIFTS_FILE, shifts)
            st.success("Shift updated.")
            st.experimental_rerun()

        if delete_btn:
            remaining = [s for s in shifts if s["id"] != selected_shift["id"]]
            save_json(SHIFTS_FILE, remaining)
            st.success("Shift deleted.")
            st.experimental_rerun()


# ---------- Main ----------

def main():
    st.set_page_config(page_title="Provider Scheduling Portal", layout="wide")

    providers, sites, shifts = load_all_data()

    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Providers", "Sites", "Shifts"],
    )

    if page == "Dashboard":
        page_dashboard(providers, sites, shifts)
    elif page == "Providers":
        page_providers(providers, sites)
    elif page == "Sites":
        page_sites(sites)
    elif page == "Shifts":
        page_shifts(providers, sites, shifts)


if __name__ == "__main__":
    main()
