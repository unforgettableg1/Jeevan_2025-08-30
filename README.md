# Jeevan_2025-08-30
# Store Monitoring – Take Home Assignment

## Problem Statement
Loop monitors several restaurants in the US and needs to check if the store is online during business hours.  
Owners want a report on uptime/downtime for the past hour, day, and week.

This project builds a backend system + API to:

- Ingest store status, business hours, and timezone data.
- Generate reports (uptime/downtime).
- Provide APIs to trigger, check status, and download reports.
- Preview a simple UI for report generation.

---

##  Repository Structure
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

## Create virtual environment & install dependencies
python -m venv .venv
.venv\Scripts\activate      # Windows

pip install -r requirements.txt


## Run the app
uvicorn app.main:app --reload
Server will start at: http://127.0.0.1:8000

## API Endpoints
POST /trigger_report → Start report generation (returns report_id)
GET /get_report?report_id=... → Check report status
GET /download_report?report_id=... → Download CSV report
Swagger Docs: http://127.0.0.1:8000/docs

## Preview UI
Visit http://127.0.0.1:8000/

## Example Output
The generated CSV has schema:
store_id, uptime_last_hour_minutes, uptime_last_day_hours, uptime_last_week_hours,
downtime_last_hour_minutes, downtime_last_day_hours, downtime_last_week_hours

