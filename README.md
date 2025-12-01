# Provider Scheduling (Streamlit)

A simple, pretty monthly calendar to share provider availability with clients in real time, with CSV import/export and a QGenda-friendly CSV.

## Deploy (no local Python required)
1. Create a new **GitHub** repository (empty).
2. Upload all files in this ZIP to the repo.
3. Go to **Streamlit Community Cloud** → New app → pick your repo → `app.py` → **Deploy**.

## Features
- Monthly calendar (FullCalendar via `streamlit-calendar`, with fallback table).
- Manage **Providers**, **Clients**, **Credentials**, and **Shifts**.
- CSV import/export and **QGenda-friendly** CSV export.
- SQLite database (auto-created in `/data`).

## CSV Templates
See files in `/imports` for examples:
- `providers.csv`: provider_id,provider_name,specialty,preferred_shift_start,preferred_shift_end,preferred_days
- `clients.csv`: client_id,client_name,location
- `credentials.csv`: provider_id,client_id
- `shifts.csv`: shift_id,provider_id,client_id,start_datetime,end_datetime,shift_type,notes

## Notes
- If the calendar component fails to load in your environment, the app falls back to a simple month table.
- To edit a shift in the MVP, delete it and re-add.
