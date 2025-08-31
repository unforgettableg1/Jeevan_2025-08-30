# Store Monitoring — Take Home (FastAPI + SQLite)

This repo contains a reference implementation of the **Store Monitoring** problem.
It ingests the three CSVs, stores them in SQLite, and provides two endpoints:

- `POST /trigger_report` — starts report generation and returns a `report_id`.
- `GET /get_report?report_id=...` — returns *Running* until ready, then *Complete* and a CSV file.

## How it works

- **Database:** SQLite via SQLAlchemy. Tables: `store_status`, `business_hours`, `store_timezone`, `reports`.
- **Time:** All *poll* timestamps are **UTC**. Business hours are given in **local** time; we convert them to UTC using the store timezone (default `America/Chicago` if missing).
- **Business hours:** If missing for a store, we assume **24x7**.
- **Now:** We define *now* as the **max timestamp** from `store_status` (static dataset). This value is used for the "last hour/day/week" windows.
- **Computation:** We compute uptime/downtime *only within business hours* using a step-function interpolation of poll samples.
  - Each observation's status holds until the next observation.
  - For window edges, we *forward-fill* from the last seen observation **at or before** the window start, if available; otherwise we *back-fill* from the earliest observation inside the window; if still unavailable we conservatively treat as **inactive**.
  - We clamp segments to business-hour intervals and sum overlaps.
  - Windows:
    - last hour: minutes
    - last day (24h): hours (float rounded to 2 decimals)
    - last week (7d): hours (float rounded to 2 decimals)

## Project layout

```
.
├── app
│   ├── main.py               # FastAPI app & endpoints
│   ├── models.py             # SQLAlchemy models
│   ├── schemas.py            # Pydantic schemas
│   ├── ingestion.py          # CSV -> DB ingestion utilities
│   ├── report_logic.py       # Core computation of uptime/downtime
│   └── utils_time.py         # Time helpers (windowing, TZ conversion, splitting ranges)
├── reports/                  # Generated CSV reports saved here
├── sample_data/              # Place the provided CSVs here (see below)
├── tests/
│   └── test_report_logic.py  # Minimal unit tests for overlap logic
├── requirements.txt
└── README.md
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Put your input CSVs here (exact filenames below)
#   sample_data/store_status.csv
#   sample_data/business_hours.csv
#   sample_data/store_timezones.csv

uvicorn app.main:app --reload
```

### Endpoints

- `POST /trigger_report`
  - Body: none
  - Returns: `{ "report_id": "<uuid>" }`
- `GET /get_report?report_id=<uuid>`
  - Returns JSON while running: `{ "status": "Running" }`
  - When complete: `{ "status": "Complete", "report_path": "<path>", "download_name": "report.csv" }` and streams the CSV.

### Expected CSV output schema

```
store_id,uptime_last_hour_minutes,uptime_last_day_hours,uptime_last_week_hours,
downtime_last_hour_minutes,downtime_last_day_hours,downtime_last_week_hours
```

> Note: The "last hour/day/week" windows are relative to the **max** timestamp in the `store_status` table (per problem statement).

## CSV filenames expected

Place the supplied CSVs in `sample_data/` with *exact* names:

- `store_status.csv` with columns: `store_id,timestamp_utc,status`
- `business_hours.csv` with columns: `store_id,dayOfWeek,start_time_local,end_time_local` (0=Monday, 6=Sunday)
- `store_timezones.csv` with columns: `store_id,timezone_str` (default `America/Chicago`)

## Ideas to improve

- Parallelize report computation (e.g., multiprocessing or async per store).
- Add indexes to DB tables on `(store_id, timestamp_utc)` for faster filtering.
- Robust handling of daylight saving transitions when converting local business hours to UTC.
- Add incremental computation using watermarks to avoid recomputation from scratch.
- Plug in a background worker (Celery/RQ) and object storage for large CSVs.
- Expand tests to cover edge cases such as open intervals crossing midnight, missing data spans, and DST changes.
- Support partial windows (e.g., custom date ranges, custom granularities).

## Demo

- A tiny synthetic dataset and one generated CSV report are included in `reports/` (created by the build script here).
- With the real dataset, run `/trigger_report` then poll `/get_report` until completion to get the full CSV.

---

**Repo name suggestion:** `{firstname}_2025-08-25`
