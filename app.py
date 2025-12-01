from __future__ import annotations
import os
import io
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta

import pandas as pd
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, DateTime, Time, ForeignKey
)
from sqlalchemy.sql import select, and_
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
APP_TITLE = "StaffOS - VISTA Provider Scheduling"
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
    Column("preferred_days", String, nullable=True),
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

def safe_select_index(series, predicate, default=0):
    try:
        idx = series.index[series.apply(predicate)][0]
        return int(idx)
    except Exception:
        return int(default)

# Color map for events (FullCalendar)
COLOR_DEFAULT = "#96caba"
COLOR_DAY = "#065b56"
COLOR_NIGHT = "#4b4f54"
COLOR_CALL24 = "#fd9074"


def parse_time(t: str | time | None) -> time | None:
    if t is None or t == "":
        return None
    if isinstance(t, time):
        return t
    for fmt in ("%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(t.strip(), fmt).time()
        except Exception:
            pass
    return None

def month_range(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    last = first + relativedelta(months=1) - timedelta(days=1)
    return first, last

def df_from_table(conn, table: Table) -> pd.DataFrame:
    rows = conn.execute(select(table)).mappings().all()
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=[c.name for c in table.columns])

def upsert(conn, table: Table, row: dict, key: str):
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
    df = pd.DataFrame(engine.begin().execute(q).mappings().all())
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
        })[[
            "ProviderID","ProviderName","ClientID","ClientName","Location",
            "StartDateTime","EndDateTime","ShiftType","Notes"
        ]]
    out_path = os.path.join(EXPORTS_DIR, f"qgenda_export_{start_dt.date()}_to_{end_dt.date()}.csv")
    df.to_csv(out_path, index=False)
    return out_path

def export_table_template(name: str) -> bytes:
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
# UI
# ----------------------

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)
st.caption("Monthly scheduling with real-time calendar, CSV import/export, and QGenda-friendly export.")

# Session defaults
if "selected_year" not in st.session_state:
    today = date.today()
    st.session_state.selected_year = today.year
    st.session_state.selected_month = today.month
if "prov_filter" not in st.session_state:
    st.session_state.prov_filter = "(All)"
if "cli_filter" not in st.session_state:
    st.session_state.cli_filter = "(All)"

with engine.begin() as conn:
    df_prov = df_from_table(conn, providers)
    df_cli = df_from_table(conn, clients)
    df_creds = df_from_table(conn, credentials)
    df_shifts = df_from_table(conn, shifts)

# Sidebar filters
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
        "Filter by Provider", options=["(All)"] + (sorted(df_prov["provider_name"].tolist()) if not df_prov.empty else []), key="prov_filter"
    ) if not df_prov.empty else "(All)"
    cli_filter = st.selectbox(
        "Filter by Client", options=["(All)"] + (sorted(df_cli["client_name"].tolist()) if not df_cli.empty else []), key="cli_filter"
    ) if not df_cli.empty else "(All)"

    safe_mode = st.toggle("Safe mode: auto-fix filters", value=True, help="Prevents crashes if a filter choice no longer exists.")

    if st.button("Clear all filters (jump to current month)"):
        today = date.today()
        st.session_state.selected_year = today.year
        st.session_state.selected_month = today.month
        st.session_state.prov_filter = "(All)"
        st.session_state.cli_filter = "(All)"
        st.rerun()
    if st.button("Clear provider/client filters only"):
        st.session_state.prov_filter = "(All)"
        st.session_state.cli_filter = "(All)"
        st.rerun()

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
        is_24h = st.checkbox("24-hour call shift", value=False, help="Ends 24 hours after start (next day).")
        end_t = st.time_input("End", value=time(16, 0), disabled=is_24h)
        shift_type = st.text_input("Shift Type", value="Call (24h)" if is_24h else "Day")
        notes = st.text_input("Notes", value="")
        submitted = st.form_submit_button("Add Shift")
        if submitted and provider_id and client_id:
            with engine.begin() as conn:
                sid = generate_id("S")
                start_dt = datetime.combine(shift_date, start_t)
                end_dt = start_dt + timedelta(hours=24) if is_24h else datetime.combine(shift_date, end_t)
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

# Reload after writes
with engine.begin() as conn:
    df_prov = df_from_table(conn, providers)
    df_cli = df_from_table(conn, clients)
    df_creds = df_from_table(conn, credentials)
    df_shifts = df_from_table(conn, shifts)

first_day, last_day = month_range(st.session_state.selected_year, st.session_state.selected_month)

# Filter shifts for month and by filters
if not df_shifts.empty:
    df_shifts = df_shifts[(df_shifts["start_datetime"] >= pd.Timestamp(first_day)) & (df_shifts["end_datetime"] <= pd.Timestamp(last_day) + pd.Timedelta(days=1))]
if prov_filter != "(All)" and not df_prov.empty:
    pid = df_prov.loc[df_prov["provider_name"] == prov_filter, "provider_id"].iloc[0] if (not df_prov.empty and (df_prov["provider_name"] == prov_filter).any()) else None
    df_shifts = df_shifts[df_shifts["provider_id"] == pid] if pid is not None else df_shifts
if cli_filter != "(All)" and not df_cli.empty:
    cid = df_cli.loc[df_cli["client_name"] == cli_filter, "client_id"].iloc[0] if (not df_cli.empty and (df_cli["client_name"] == cli_filter).any()) else None
    df_shifts = df_shifts[df_shifts["client_id"] == cid] if cid is not None else df_shifts


# Auto-fix broken filters
if safe_mode:
    if prov_filter != "(All)" and (df_prov.empty or not (df_prov["provider_name"] == prov_filter).any()):
        st.session_state.prov_filter = "(All)"
        st.info("Provider filter was invalid and has been reset to (All).")
        st.rerun()
    if cli_filter != "(All)" and (df_cli.empty or not (df_cli["client_name"] == cli_filter).any()):
        st.session_state.cli_filter = "(All)"
        st.info("Client filter was invalid and has been reset to (All).")
        st.rerun()

# Tabs
tab_calendar, tab_shifts_table, tab_providers, tab_clients, tab_credentials, tab_io, tab_settings = st.tabs([
    "📅 Calendar", "📋 Shifts (Table)", "👩‍⚕️ Providers", "🏥 Clients", "🔐 Credentials", "⬆️⬇️ Upload/Download", "⚙️ Settings"
])

# Calendar
with tab_calendar:
    st.subheader(f"Monthly View — {first_day.strftime('%B %Y')}")
    with st.expander("Debug: Show raw shifts for this month"):
        st.dataframe(df_shifts, use_container_width=True, hide_index=True)

    # Build events for the calendar
    events = []
    if not df_shifts.empty:
        pmap = {r["provider_id"]: r["provider_name"] for _, r in df_prov.iterrows()} if not df_prov.empty else {}
        cmap = {r["client_id"]: r["client_name"] for _, r in df_cli.iterrows()} if not df_cli.empty else {}
        for _, r in df_shifts.iterrows():
            prov_name = pmap.get(r["provider_id"], "Unknown Provider")
            cli_name = cmap.get(r["client_id"], "Unknown Client")
            title = f"{prov_name} @ {cli_name} ({r['shift_type']})" if r.get("shift_type") else f"{prov_name} @ {cli_name}"
            duration_hours = (pd.to_datetime(r["end_datetime"]) - pd.to_datetime(r["start_datetime"])).total_seconds() / 3600.0
            if abs(duration_hours - 24.0) < 0.01:
                color = COLOR_CALL24
            elif isinstance(r.get("shift_type"), str) and "night" in r.get("shift_type","").lower():
                color = COLOR_NIGHT
            elif isinstance(r.get("shift_type"), str) and "day" in r.get("shift_type","").lower():
                color = COLOR_DAY
            else:
                color = COLOR_DEFAULT
            events.append({
                "title": title,
                "start": pd.to_datetime(r["start_datetime"]).isoformat(),
                "end": pd.to_datetime(r["end_datetime"]).isoformat(),
                "color": color,
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
            "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"},
            "height": 720,
        }
        with st.container():
            cal_state = st_calendar(events=events, options=cal_options, key="main_calendar")
            # Legend
            st.markdown("**Legend**")
            lc1, lc2, lc3, lc4 = st.columns(4)
            with lc1:
                st.markdown(f'<div style="display:flex;align-items:center;"><span style="width:14px;height:14px;background:{COLOR_DEFAULT};display:inline-block;margin-right:8px;border-radius:3px;"></span>Other</div>', unsafe_allow_html=True)
            with lc2:
                st.markdown(f'<div style="display:flex;align-items:center;"><span style="width:14px;height:14px;background:{COLOR_DAY};display:inline-block;margin-right:8px;border-radius:3px;"></span>Day</div>', unsafe_allow_html=True)
            with lc3:
                st.markdown(f'<div style="display:flex;align-items:center;"><span style="width:14px;height:14px;background:{COLOR_NIGHT};display:inline-block;margin-right:8px;border-radius:3px;"></span>Night</div>', unsafe_allow_html=True)
            with lc4:
                st.markdown(f'<div style="display:flex;align-items:center;"><span style="width:14px;height:14px;background:{COLOR_CALL24};display:inline-block;margin-right:8px;border-radius:3px;"></span>24h Call</div>', unsafe_allow_html=True)

            if cal_state and cal_state.get("clickedEvent"):
                ev = cal_state["clickedEvent"]
                st.info(f"Selected: {ev['title']}")

                sid = ev["extendedProps"]["shift_id"]
                prov_id = ev["extendedProps"]["provider_id"]
                cli_id = ev["extendedProps"]["client_id"]
                notes_val = ev["extendedProps"].get("notes", "")
                start_val = pd.to_datetime(ev["start"]).to_pydatetime()
                end_val = pd.to_datetime(ev["end"]).to_pydatetime()

                with st.form(f"edit_shift_{sid}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        prov_options = df_prov["provider_name"].tolist() if not df_prov.empty else ["(none)"]
                        prov_index = 0
                        if not df_prov.empty and (df_prov["provider_id"] == prov_id).any():
                            prov_index = int(df_prov.index[df_prov["provider_id"]==prov_id][0])
                        prov_name_edit = st.selectbox("Provider", options=prov_options, index=min(prov_index, max(len(prov_options)-1,0)))
                    with c2:
                        cli_options = df_cli["client_name"].tolist() if not df_cli.empty else ["(none)"]
                        cli_index = 0
                        if not df_cli.empty and (df_cli["client_id"] == cli_id).any():
                            cli_index = int(df_cli.index[df_cli["client_id"]==cli_id][0])
                        cli_name_edit = st.selectbox("Client", options=cli_options, index=min(cli_index, max(len(cli_options)-1,0)))
                    c3, c4 = st.columns(2)
                    with c3:
                        start_date_edit = st.date_input("Start Date", value=start_val.date())
                        start_time_edit = st.time_input("Start Time", value=start_val.time())
                    with c4:
                        is_24h_edit = st.checkbox("24-hour call shift (edit)", value=(end_val - start_val).total_seconds() == 24*3600)
                        end_date_edit = st.date_input("End Date", value=end_val.date(), disabled=is_24h_edit)
                        end_time_edit = st.time_input("End Time", value=end_val.time(), disabled=is_24h_edit)

                    default_type = "Day"
                    if "(" in ev.get("title","") and ev["title"].endswith(")"):
                        default_type = ev["title"].split("(")[-1].rstrip(")")
                    shift_type_edit = st.text_input("Shift Type", value=default_type)
                    notes_edit = st.text_input("Notes", value=notes_val)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        save = st.form_submit_button("Save changes")
                    with col2:
                        dup = st.form_submit_button("Duplicate")
                    with col3:
                        delete = st.form_submit_button("Delete")

                if delete:
                    with engine.begin() as conn:
                        delete_by_id(conn, shifts, "shift_id", sid)
                    st.success("Deleted shift.")
                    st.rerun()

                if save or dup:
                    new_prov_id = df_prov.loc[df_prov["provider_name"] == prov_name_edit, "provider_id"].iloc[0] if prov_name_edit in (df_prov["provider_name"].tolist() if not df_prov.empty else []) else prov_id
                    new_cli_id = df_cli.loc[df_cli["client_name"] == cli_name_edit, "client_id"].iloc[0] if cli_name_edit in (df_cli["client_name"].tolist() if not df_cli.empty else []) else cli_id
                    start_dt_new = datetime.combine(start_date_edit, start_time_edit)
                    if is_24h_edit:
                        end_dt_new = start_dt_new + timedelta(hours=24)
                    else:
                        end_dt_new = datetime.combine(end_date_edit, end_time_edit)

                    row = {
                        "shift_id": sid if save else generate_id("S"),
                        "provider_id": new_prov_id,
                        "client_id": new_cli_id,
                        "start_datetime": start_dt_new,
                        "end_datetime": end_dt_new,
                        "shift_type": shift_type_edit,
                        "notes": notes_edit,
                    }
                    with engine.begin() as conn:
                        upsert(conn, shifts, row, key="shift_id")
                    st.success("Saved." if save else "Duplicated.")
                    st.rerun()
            else:
                st.info("Tip: click a calendar event to edit it. If clicking doesn't open a form, use the selector below.")
                if events:
                    options = []
                    for e in events:
                        s_val = pd.to_datetime(e["start"]).strftime("%Y-%m-%d %H:%M")
                        e_val = pd.to_datetime(e["end"]).strftime("%Y-%m-%d %H:%M")
                        title = e.get("title","")
                        label = f"{s_val} → {e_val} | {title} [{e['extendedProps']['shift_id']}]"
                        options.append((label, e["extendedProps"]["shift_id"]))
                    labels = [o[0] for o in options]
                    ids = {o[0]: o[1] for o in options}

                    selected_label = st.selectbox("Select a shift to edit (Calendar tab)", options=labels)
                    selected_id = ids[selected_label]

                    with engine.begin() as conn:
                        row = conn.execute(select(shifts).where(shifts.c.shift_id == selected_id)).mappings().first()

                    if row:
                        with st.form(f"edit_shift_calendar_fallback_{selected_id}"):
                            c1, c2 = st.columns(2)
                            with c1:
                                prov_options = df_prov["provider_name"].tolist() if not df_prov.empty else ["(none)"]
                                prov_index = 0
                                if not df_prov.empty and (df_prov["provider_id"] == row["provider_id"]).any():
                                    prov_index = int(df_prov.index[df_prov["provider_id"]==row["provider_id"]][0])
                                prov_name_edit = st.selectbox("Provider", options=prov_options, index=min(prov_index, max(len(prov_options)-1,0)))
                            with c2:
                                cli_options = df_cli["client_name"].tolist() if not df_cli.empty else ["(none)"]
                                cli_index = 0
                                if not df_cli.empty and (df_cli["client_id"] == row["client_id"]).any():
                                    cli_index = int(df_cli.index[df_cli["client_id"]==row["client_id"]][0])
                                cli_name_edit = st.selectbox("Client", options=cli_options, index=min(cli_index, max(len(cli_options)-1,0)))

                            start_val2 = pd.to_datetime(row["start_datetime"]).to_pydatetime()
                            end_val2 = pd.to_datetime(row["end_datetime"]).to_pydatetime()

                            c3, c4 = st.columns(2)
                            with c3:
                                start_date_edit = st.date_input("Start Date", value=start_val2.date())
                                start_time_edit = st.time_input("Start Time", value=start_val2.time())
                            with c4:
                                is_24h_edit = st.checkbox("24-hour call shift", value=(end_val2 - start_val2).total_seconds() == 24*3600)
                                end_date_edit = st.date_input("End Date", value=end_val2.date(), disabled=is_24h_edit)
                                end_time_edit = st.time_input("End Time", value=end_val2.time(), disabled=is_24h_edit)

                            shift_type_edit = st.text_input("Shift Type", value=row.get("shift_type") or "Day")
                            notes_edit = st.text_input("Notes", value=row.get("notes") or "")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                save = st.form_submit_button("Save changes")
                            with col2:
                                dup = st.form_submit_button("Duplicate")
                            with col3:
                                delete = st.form_submit_button("Delete")

                        if delete:
                            with engine.begin() as conn:
                                delete_by_id(conn, shifts, "shift_id", selected_id)
                            st.success("Deleted shift.")
                            st.rerun()

                        if save or dup:
                            new_prov_id = df_prov.loc[df_prov["provider_name"] == prov_name_edit, "provider_id"].iloc[0] if prov_name_edit in (df_prov["provider_name"].tolist() if not df_prov.empty else []) else row["provider_id"]
                            new_cli_id = df_cli.loc[df_cli["client_name"] == cli_name_edit, "client_id"].iloc[0] if cli_name_edit in (df_cli["client_name"].tolist() if not df_cli.empty else []) else row["client_id"]
                            start_dt_new = datetime.combine(start_date_edit, start_time_edit)
                            if is_24h_edit:
                                end_dt_new = start_dt_new + timedelta(hours=24)
                            else:
                                end_dt_new = datetime.combine(end_date_edit, end_time_edit)

                            new_row = {
                                "shift_id": selected_id if save else generate_id("S"),
                                "provider_id": new_prov_id,
                                "client_id": new_cli_id,
                                "start_datetime": start_dt_new,
                                "end_datetime": end_dt_new,
                                "shift_type": shift_type_edit,
                                "notes": notes_edit,
                            }
                            with engine.begin() as conn:
                                upsert(conn, shifts, new_row, key="shift_id")
                            st.success("Saved." if save else "Duplicated.")
                            st.rerun()
    else:
        st.warning("Calendar component not available — showing simple month table.")
        days = pd.date_range(first_day, last_day, freq="D")
        table = pd.DataFrame(index=[d.date() for d in days], columns=["Shifts"]).fillna("")
        for _, r in df_shifts.iterrows():
            d = pd.to_datetime(r["start_datetime"]).date()
            prov_name = df_prov.loc[df_prov["provider_id"] == r["provider_id"], "provider_name"].iloc[0] if not df_prov.empty else "Unknown"
            cli_name = df_cli.loc[df_cli["client_id"] == r["client_id"], "client_name"].iloc[0] if not df_cli.empty else "Unknown"
            table.at[d, "Shifts"] += f"• {prov_name} @ {cli_name} ({r.get('shift_type','')})\n"
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
            path = export_qgenda_csv(engine.begin(), datetime.combine(start, time.min), datetime.combine(end, time.max))
            st.success(f"Exported to {path}")
            with open(path, "rb") as f:
                st.download_button("Download CSV", f, file_name=os.path.basename(path), mime="text/csv")
with tab_shifts_table:
    st.subheader("Shifts — Current Month (Filtered)")

    def attach_names(df):
        if df.empty:
            return df
        pmap = {r["provider_id"]: r["provider_name"] for _, r in df_prov.iterrows()} if not df_prov.empty else {}
        cmap = {r["client_id"]: r["client_name"] for _, r in df_cli.iterrows()} if not df_cli.empty else {}
        out = df.copy()
        out["Provider"] = out["provider_id"].map(pmap)
        out["Client"] = out["client_id"].map(cmap)
        out["Start"] = pd.to_datetime(out["start_datetime"]).dt.strftime("%Y-%m-%d %H:%M")
        out["End"] = pd.to_datetime(out["end_datetime"]).dt.strftime("%Y-%m-%d %H:%M")
        return out[["shift_id","Provider","Client","Start","End","shift_type","notes"]]

    table_df = attach_names(df_shifts)
    st.dataframe(table_df, use_container_width=True, hide_index=True)
    st.caption("Tip: Use the editor below to modify a specific shift directly from this tab.")

    # --- Inline editor ---
    if not table_df.empty:
        # Build a readable label for each shift to choose from
        options = []
        for _, r in table_df.iterrows():
            label = f"{r['Start']} → {r['End']} | {r['Provider']} @ {r['Client']} | {r['shift_type']} [{r['shift_id']}]"
            options.append((label, r["shift_id"]))
        labels = [o[0] for o in options]
        ids = {o[0]: o[1] for o in options}

        selected_label = st.selectbox("Select a shift to edit", options=labels)
        selected_id = ids[selected_label]

        # Load the raw row for the selected shift from DB
        with engine.begin() as conn:
            row = conn.execute(select(shifts).where(shifts.c.shift_id == selected_id)).mappings().first()

        if row:
            st.markdown("#### Edit Shift")
            with st.form(f"edit_shift_inline_{selected_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    prov_name_edit = st.selectbox("Provider", options=df_prov["provider_name"].tolist(),
                                                  index=int(df_prov.index[df_prov["provider_id"]==row["provider_id"]][0]))
                with c2:
                    cli_name_edit = st.selectbox("Client", options=df_cli["client_name"].tolist(),
                                                 index=int(df_cli.index[df_cli["client_id"]==row["client_id"]][0]))

                start_val = pd.to_datetime(row["start_datetime"]).to_pydatetime()
                end_val = pd.to_datetime(row["end_datetime"]).to_pydatetime()

                c3, c4 = st.columns(2)
                with c3:
                    start_date_edit = st.date_input("Start Date", value=start_val.date())
                    start_time_edit = st.time_input("Start Time", value=start_val.time())
                with c4:
                    is_24h_edit = st.checkbox("24-hour call shift", value=(end_val - start_val).total_seconds() == 24*3600)
                    end_date_edit = st.date_input("End Date", value=end_val.date(), disabled=is_24h_edit)
                    end_time_edit = st.time_input("End Time", value=end_val.time(), disabled=is_24h_edit)

                shift_type_edit = st.text_input("Shift Type", value=row.get("shift_type") or "Day")
                notes_edit = st.text_input("Notes", value=row.get("notes") or "")

                col1, col2, col3 = st.columns(3)
                with col1:
                    save = st.form_submit_button("Save changes")
                with col2:
                    dup = st.form_submit_button("Duplicate")
                with col3:
                    delete = st.form_submit_button("Delete")

            if delete:
                with engine.begin() as conn:
                    delete_by_id(conn, shifts, "shift_id", selected_id)
                st.success("Deleted shift.")
                st.rerun()

            if save or dup:
                new_prov_id = df_prov.loc[df_prov["provider_name"] == prov_name_edit, "provider_id"].iloc[0]
                new_cli_id = df_cli.loc[df_cli["client_name"] == cli_name_edit, "client_id"].iloc[0]
                start_dt_new = datetime.combine(start_date_edit, start_time_edit)
                if is_24h_edit:
                    end_dt_new = start_dt_new + timedelta(hours=24)
                else:
                    end_dt_new = datetime.combine(end_date_edit, end_time_edit)

                new_row = {
                    "shift_id": selected_id if save else generate_id("S"),
                    "provider_id": new_prov_id,
                    "client_id": new_cli_id,
                    "start_datetime": start_dt_new,
                    "end_datetime": end_dt_new,
                    "shift_type": shift_type_edit,
                    "notes": notes_edit,
                }
                with engine.begin() as conn:
                    upsert(conn, shifts, new_row, key="shift_id")
                st.success("Saved." if save else "Duplicated.")
                st.rerun()
    else:
        st.info("No shifts in the current month after filters. Try clearing filters or switching months.")


    def attach_names(df):
        if df.empty:
            return df
        pmap = {r["provider_id"]: r["provider_name"] for _, r in df_prov.iterrows()} if not df_prov.empty else {}
        cmap = {r["client_id"]: r["client_name"] for _, r in df_cli.iterrows()} if not df_cli.empty else {}
        out = df.copy()
        out["Provider"] = out["provider_id"].map(pmap)
        out["Client"] = out["client_id"].map(cmap)
        out["Start"] = pd.to_datetime(out["start_datetime"]).dt.strftime("%Y-%m-%d %H:%M")
        out["End"] = pd.to_datetime(out["end_datetime"]).dt.strftime("%Y-%m-%d %H:%M")
        return out[["shift_id","Provider","Client","Start","End","shift_type","notes"]]

    st.dataframe(attach_names(df_shifts), use_container_width=True, hide_index=True)
    st.caption("If your event is missing from the Calendar, check here first.")

# Providers
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
                st.rerun()
    st.markdown("### Current Providers")
    with engine.begin() as conn:
        st.dataframe(df_from_table(conn, providers), use_container_width=True, hide_index=True)

# Clients
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
                st.rerun()
    st.markdown("### Current Clients")
    with engine.begin() as conn:
        st.dataframe(df_from_table(conn, clients), use_container_width=True, hide_index=True)

# Credentials
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
                st.rerun()
    st.markdown("### Current Credentials")
    with engine.begin() as conn:
        st.dataframe(df_from_table(conn, credentials), use_container_width=True, hide_index=True)

# Upload / Download
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
            st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        handle_import("providers", providers, key_col="provider_id")
        handle_import("clients", clients, key_col="client_id")
    with c2:
        handle_import("credentials", credentials)
        handle_import("shifts", shifts, key_col="shift_id")

# Settings
with tab_settings:
    st.subheader("Display & Behavior")
    st.caption("Tweak the look and defaults.")
    st.toggle("Use 24-hour time (labels only)", value=True)
    st.write("Theme colors can be adjusted in `.streamlit/config.toml`.")
