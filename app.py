from __future__ import annotations
import os
import io
import json
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, DateTime, Time, ForeignKey
)
from sqlalchemy.sql import select, and_, func
from sqlalchemy.exc import OperationalError

import streamlit as st

# Attempt to import the calendar component
CAL_AVAILABLE = True
try:
    from streamlit_calendar import calendar as st_calendar
except Exception:
    CAL_AVAILABLE = False

# ----------------------
# Configuration & Paths
# ----------------------
APP_TITLE = "Provider Scheduling"
DB_PATH = os.path.join("data", "scheduling.db")
EXPORTS_DIR = "exports"
IMPORTS_DIR = "imports"
os.makedirs("data", exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(IMPORTS_DIR, exist_ok=True)

# ----------------------
# Database Setup (SQLite)
# ----------------------
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
metadata = MetaData()

providers = Table(
    "providers", metadata,
    Column("provider_id", String, primary_key=True),
    Column("provider_name", String, nullable=False),
    Column("specialty", String, nullable=True),
    Column("preferred_shift_start", Time, nullable=True),
    Column("preferred_shift_end", Time, nullable=True),
    Column("preferred_days", String, nullable=True),  # e.g. "Mon,Tue,Wed"
)

clients = Table(
    "clients", metadata,
    Column("client_id", String, primary_key=True),
    Column("client_name", String, nullable=False),
    Column("location", String, nullable=True),
)

credentials = Table(
    "credentials", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider_id", String, ForeignKey("providers.provider_id"), nullable=False),
    Column("client_id", String, ForeignKey("clients.client_id"), nullable=False),
)

shifts = Table(
    "shifts", metadata,
    Column("shift_id", String, primary_key=True),
    Column("provider_id", String, ForeignKey("providers.provider_id"), nullable=False),
    Column("client_id", String, ForeignKey("clients.client_id"), nullable=False),
    Column("start_datetime", DateTime, nullable=False),
    Column("end_datetime", DateTime, nullable=False),
    Column("shift_type", String, nullable=True),
    Column("notes", String, nullable=True),
)

with engine.begin() as conn:
    metadata.create_all(conn)

# ----------------------
# Helpers
# ----------------------

def parse_time(t: str | time | None) -> time | None:
    if t is None or t == "":
        return None
    if isinstance(t, time):
        return t
    try:
        return datetime.strptime(t.strip(), "%H:%M").time()
    except Exception:
        try:
            return datetime.strptime(t.strip(), "%I:%M %p").time()
        except Exception:
            return None


def month_range(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = first + relativedelta(months=1) - timedelta(days=1)
    return first, last


def df_from_table(conn, table: Table) -> pd.DataFrame:
    rows = conn.execute(select(table)).mappings().all()
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[c.name for c in table.columns])


def upsert(conn, table: Table, row: dict, key: str):
    # Simple upsert for SQLite
    existing = conn.execute(select(table).where(table.c[key] == row[key])).mappings().first()
    if existing:
        conn.execute(table.update().where(table.c[key] == row[key]).values(**row))
    else:
        conn.execute(table.insert().values(**row))


def delete_by_id(conn, table: Table, key: str, value: str):
    conn.execute(table.delete().where(getattr(table.c, key) == value))


def generate_id(prefix: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}_{ts}"


def human_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

# ----------------------
# Exporters
# ----------------------

def export_qgenda_csv(conn, start_dt: datetime, end_dt: datetime) -> str:
    q = (
        select(
            shifts.c.shift_id,
            shifts.c.provider_id,
            providers.c.provider_name,
            shifts.c.client_id,
            clients.c.client_name,
            clients.c.location,
            shifts.c.start_datetime,
            shifts.c.end_datetime,
            shifts.c.shift_type,
            shifts.c.notes,
        )
        .select_from(shifts.join(providers, shifts.c.provider_id == providers.c.provider_id)
                     .join(clients, shifts.c.client_id == clients.c.client_id))
        .where(and_(shifts.c.start_datetime >= start_dt, shifts.c.end_datetime <= end_dt))
        .order_by(shifts.c.start_datetime)
    )
    df = pd.DataFrame(conn.execute(q).mappings().all())
    if df.empty:
        df = pd.DataFrame(columns=[
            "ProviderID","ProviderName","ClientID","ClientName","Location",
            "StartDateTime","EndDateTime","ShiftType","Notes"
        ])
    else:
        df = df.rename(columns={
            "provider_id": "ProviderID",
            "provider_name": "ProviderName",
            "client_id": "ClientID",
            "client_name": "ClientName",
            "location": "Location",
            "start_datetime": "StartDateTime",
            "end_datetime": "EndDateTime",
            "shift_type": "ShiftType",
            "notes": "Notes",
        })[
            [
                "ProviderID","ProviderName","ClientID","ClientName","Location",
                "StartDateTime","EndDateTime","ShiftType","Notes"
            ]
        ]
    out_path = os.path.join(EXPORTS_DIR, f"qgenda_export_{start_dt.date()}_to_{end_dt.date()}.csv")
    df.to_csv(out_path, index=False)
    return out_path


def export_table_template(name: str) -> bytes:
    import io
    templates = {
        "providers": pd.DataFrame([
            {
                "provider_id": "P001",
                "provider_name": "Dr. Alice Stone",
                "specialty": "Cardiology",
                "preferred_shift_start": "08:00",
                "preferred_shift_end": "16:00",
                "preferred_days": "Mon,Tue,Wed"
            }
        ]),
        "clients": pd.DataFrame([
            {"client_id": "C001", "client_name": "Riverside Hospital", "location": "Austin, TX"}
        ]),
        "credentials": pd.DataFrame([
            {"provider_id": "P001", "client_id": "C001"}
        ]),
        "shifts": pd.DataFrame([
            {
                "shift_id": "S001",
                "provider_id": "P001",
                "client_id": "C001",
                "start_datetime": "2025-01-10 08:00",
                "end_datetime": "2025-01-10 16:00",
                "shift_type": "Day",
                "notes": ""
            }
        ]),
    }
    buf = io.StringIO()
    templates[name].to_csv(buf, index=False)
    return buf.getvalue().encode()

# ----------------------
# UI Building Blocks
# ----------------------

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Fast, friendly monthly scheduling for providers and clients. Import/Export CSV, QGenda-friendly export, and a real-time calendar view.")

# Session defaults
if "selected_year" not in st.session_state:
    today = date.today()
    st.session_state.selected_year = today.year
    st.session_state.selected_month = today.month

with engine.begin() as conn:
    df_prov = df_from_table(conn, providers)
    df_cli = df_from_table(conn, clients)
    df_creds = df_from_table(conn, credentials)
    df_shifts = df_from_table(conn, shifts)

# Filters & Month Picker
with st.sidebar:
    st.subheader("Filters & Month")
    col_a, col_b = st.columns(2)
    with col_a:
        year = st.number_input("Year", min_value=2000, max_value=2100, value=st.session_state.selected_year, step=1)
    with col_b:
        month = st.number_input("Month", min_value=1, max_value=12, value=st.session_state.selected_month, step=1)
    st.session_state.selected_year = year
    st.session_state.selected_month = month

    prov_filter = st.selectbox(
        "Filter by Provider", options=["(All)"] + sorted(df_prov["provider_name"].tolist())
    ) if not df_prov.empty else "(All)"

    cli_filter = st.selectbox(
        "Filter by Client", options=["(All)"] + sorted(df_cli["client_name"].tolist())
    ) if not df_cli.empty else "(All)"

    st.markdown("---")
    st.subheader("Quick Add Shift")
    with st.form("quick_add_shift"):
        provider_id = None
        client_id = None
        if df_prov.empty or df_cli.empty:
            st.info("Add providers and clients first in their tabs below.")
        else:
            prov_name = st.selectbox("Provider", options=df_prov["provider_name"].tolist())
            provider_id = df_prov.loc[df_prov["provider_name"] == prov_name, "provider_id"].iloc[0]
            cli_name = st.selectbox("Client", options=df_cli["client_name"].tolist())
            client_id = df_cli.loc[df_cli["client_name"] == cli_name, "client_id"].iloc[0]

        shift_date = st.date_input("Date", value=date.today())
        start_t = st.time_input("Start", value=time(8, 0))
        end_t = st.time_input("End", value=time(16, 0))
        shift_type = st.text_input("Shift Type", value="Day")
        notes = st.text_input("Notes", value="")
        submitted = st.form_submit_button("Add Shift")
        if submitted and provider_id and client_id:
            with engine.begin() as conn:
                sid = generate_id("S")
                start_dt = datetime.combine(shift_date, start_t)
                end_dt = datetime.combine(shift_date, end_t)
                upsert(conn, shifts, {
                    "shift_id": sid,
                    "provider_id": provider_id,
                    "client_id": client_id,
                    "start_datetime": start_dt,
                    "end_datetime": end_dt,
                    "shift_type": shift_type,
                    "notes": notes,
                }, key="shift_id")
            st.success("Shift added.")
            st.rerun()

# Re-load after potential write
with engine.begin() as conn:
    df_prov = df_from_table(conn, providers)
    df_cli = df_from_table(conn, clients)
    df_creds = df_from_table(conn, credentials)
    df_shifts = df_from_table(conn, shifts)

first_day, last_day = month_range(st.session_state.selected_year, st.session_state.selected_month)

# Apply filters to shifts
if not df_shifts.empty:
    df_shifts = df_shifts[(df_shifts["start_datetime"] >= pd.Timestamp(first_day)) & (df_shifts["end_datetime"] <= pd.Timestamp(last_day) + pd.Timedelta(days=1))]
if prov_filter != "(All)" and not df_prov.empty:
    pid = df_prov.loc[df_prov["provider_name"] == prov_filter, "provider_id"].iloc[0]
    df_shifts = df_shifts[df_shifts["provider_id"] == pid]
if cli_filter != "(All)" and not df_cli.empty:
    cid = df_cli.loc[df_cli["client_name"] == cli_filter, "client_id"].iloc[0]
    df_shifts = df_shifts[df_shifts["client_id"] == cid]

# ---------------
# Tabs Navigation
# ---------------

tab_calendar, tab_providers, tab_clients, tab_credentials, tab_io, tab_settings = st.tabs([
    "📅 Calendar", "👩‍⚕️ Providers", "🏥 Clients", "🔐 Credentials", "⬆️⬇️ Upload/Download", "⚙️ Settings"
])

# ---------
# Calendar
# ---------
with tab_calendar:
    st.subheader(f"Monthly View — {first_day.strftime('%B %Y')}")

    # Build FullCalendar events
    events = []
    if not df_shifts.empty:
        for _, r in df_shifts.iterrows():
            prov_name = df_prov.loc[df_prov["provider_id"] == r["provider_id"], "provider_name"].iloc[0]
            cli_name = df_cli.loc[df_cli["client_id"] == r["client_id"], "client_name"].iloc[0]
            title = f"{prov_name} @ {cli_name} ({r['shift_type']})"
            events.append({
                "title": title,
                "start": pd.to_datetime(r["start_datetime"]).isoformat(),
                "end": pd.to_datetime(r["end_datetime"]).isoformat(),
                "extendedProps": {
                    "shift_id": r["shift_id"],
                    "provider_id": r["provider_id"],
                    "client_id": r["client_id"],
                    "notes": r.get("notes", "")
                }
            })

    if CAL_AVAILABLE:
        cal_options = {
            "initialView": "dayGridMonth",
            "initialDate": first_day.isoformat(),
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
            },
            "height": 720,
        }
        with st.container():
            cal_state = st_calendar(events=events, options=cal_options, key="main_calendar")
            if cal_state and cal_state.get("clickedEvent"):
                ev = cal_state["clickedEvent"]
                st.info(f"Selected: {ev['title']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Delete Shift", use_container_width=True):
                        with engine.begin() as conn:
                            delete_by_id(conn, shifts, "shift_id", ev["extendedProps"]["shift_id"])
                        st.success("Deleted.")
                        st.experimental_rerun()
                with col2:
                    st.write("(Edit flow can be added similarly — to keep MVP simple.)")
    else:
        # Fallback simple month table
        st.warning("Calendar component not available — showing simple month table.")
        import pandas as pd
        days = pd.date_range(first_day, last_day, freq="D")
        table = pd.DataFrame(index=[d.date() for d in days], columns=["Shifts"]).fillna("")
        for _, r in df_shifts.iterrows():
            d = pd.to_datetime(r["start_datetime"]).date()
            prov_name = df_prov.loc[df_prov["provider_id"] == r["provider_id"], "provider_name"].iloc[0]
            cli_name = df_cli.loc[df_cli["client_id"] == r["client_id"], "client_name"].iloc[0]
            table.at[d, "Shifts"] += f"• {prov_name} @ {cli_name} ({r['shift_type']})\n"
        st.dataframe(table, use_container_width=True, height=600)

    st.markdown("---")
    st.subheader("Export")
    colx, coly, colz = st.columns(3)
    with colx:
        start = st.date_input("Export Start", value=first_day)
    with coly:
        end = st.date_input("Export End", value=last_day)
    with colz:
        if st.button("Export QGenda-friendly CSV", use_container_width=True):
            with engine.begin() as conn:
                path = export_qgenda_csv(conn, datetime.combine(start, time.min), datetime.combine(end, time.max))
            st.success(f"Exported to {path}")
            with open(path, "rb") as f:
                st.download_button("Download CSV", f, file_name=os.path.basename(path), mime="text/csv")

# ----------
# Providers
# ----------
with tab_providers:
    st.subheader("Manage Providers")
    with st.form("add_provider"):
        c1, c2, c3 = st.columns(3)
        with c1:
            pid = st.text_input("Provider ID", value="")
        with c2:
            pname = st.text_input("Name", value="")
        with c3:
            spec = st.text_input("Specialty", value="")
        c4, c5, c6 = st.columns(3)
        with c4:
            pstart = st.text_input("Preferred Start (HH:MM)", value="08:00")
        with c5:
            pend = st.text_input("Preferred End (HH:MM)", value="16:00")
        with c6:
            pdays = st.text_input("Preferred Days (e.g., Mon,Tue,Wed)", value="Mon,Tue,Wed")
        submitted = st.form_submit_button("Save Provider")
        if submitted:
            if not pid or not pname:
                st.error("Provider ID and Name are required.")
            else:
                with engine.begin() as conn:
                    upsert(conn, providers, {
                        "provider_id": pid,
                        "provider_name": pname,
                        "specialty": spec,
                        "preferred_shift_start": parse_time(pstart),
                        "preferred_shift_end": parse_time(pend),
                        "preferred_days": pdays,
                    }, key="provider_id")
                st.success("Saved provider.")
                st.experimental_rerun()

    st.markdown("### Current Providers")
    st.dataframe(df_prov, use_container_width=True, hide_index=True)

# ---------
# Clients
# ---------
with tab_clients:
    st.subheader("Manage Clients")
    with st.form("add_client"):
        c1, c2, c3 = st.columns(3)
        with c1:
            cid = st.text_input("Client ID", value="")
        with c2:
            cname = st.text_input("Client Name", value="")
        with c3:
            loc = st.text_input("Location", value="")
        submitted = st.form_submit_button("Save Client")
        if submitted:
            if not cid or not cname:
                st.error("Client ID and Name are required.")
            else:
                with engine.begin() as conn:
                    upsert(conn, clients, {
                        "client_id": cid,
                        "client_name": cname,
                        "location": loc,
                    }, key="client_id")
                st.success("Saved client.")
                st.experimental_rerun()

    st.markdown("### Current Clients")
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

# -------------
# Credentials
# -------------
with tab_credentials:
    st.subheader("Credential Providers to Clients")

    if df_prov.empty or df_cli.empty:
        st.info("Add providers and clients first.")
    else:
        with st.form("add_cred"):
            c1, c2 = st.columns(2)
            with c1:
                prov_name = st.selectbox("Provider", options=df_prov["provider_name"].tolist())
                provider_id = df_prov.loc[df_prov["provider_name"] == prov_name, "provider_id"].iloc[0]
            with c2:
                cli_name = st.selectbox("Client", options=df_cli["client_name"].tolist())
                client_id = df_cli.loc[df_cli["client_name"] == cli_name, "client_id"].iloc[0]
            submitted = st.form_submit_button("Add Credential")
            if submitted:
                with engine.begin() as conn:
                    conn.execute(credentials.insert().values(provider_id=provider_id, client_id=client_id))
                st.success("Credential added.")
                st.experimental_rerun()

    st.markdown("### Current Credentials")
    st.dataframe(df_creds, use_container_width=True, hide_index=True)

# -------------------
# Upload / Download
# -------------------
with tab_io:
    st.subheader("Download CSV Templates")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.download_button("providers.csv", data=export_table_template("providers"), file_name="providers.csv")
    with c2:
        st.download_button("clients.csv", data=export_table_template("clients"), file_name="clients.csv")
    with c3:
        st.download_button("credentials.csv", data=export_table_template("credentials"), file_name="credentials.csv")
    with c4:
        st.download_button("shifts.csv", data=export_table_template("shifts"), file_name="shifts.csv")

    st.markdown("---")
    st.subheader("Import CSVs")
    st.caption("Upload one table at a time. Column names must match the template exactly.")

    def handle_import(label: str, table: "Table", key_col: str | None = None):
        up = st.file_uploader(label, type=["csv"], key=f"up_{label}")
        if up is not None:
            df = pd.read_csv(up)
            with engine.begin() as conn:
                if key_col:
                    for _, r in df.iterrows():
                        upsert(conn, table, r.to_dict(), key=key_col)
                else:
                    conn.execute(table.insert(), df.to_dict(orient="records"))
            st.success(f"Imported {len(df)} rows into {label}.")

    c1, c2 = st.columns(2)
    with c1:
        handle_import("providers", providers, key_col="provider_id")
        handle_import("clients", clients, key_col="client_id")
    with c2:
        handle_import("credentials", credentials)
        handle_import("shifts", shifts, key_col="shift_id")

# ---------
# Settings
# ---------
with tab_settings:
    st.subheader("Display & Behavior")
    st.caption("Tweak the look and defaults.")
    st.toggle("Use 24-hour time (affects labels only)", value=True)
    st.write("Theme adjustments can be set in `.streamlit/config.toml` for brand colors.")

st.markdown("""
---
**Tips**
- Use the sidebar to filter by provider or client and to quickly add a shift.
- The calendar is interactive: click an event to select it, then delete from the panel shown.
- For QGenda uploads, export the CSV for the right date range, then map columns in QGenda's import wizard.
- Need to edit a shift? Delete it, then re-add (MVP). You can extend the app to include inline editing.
""")
