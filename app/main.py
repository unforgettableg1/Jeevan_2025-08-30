from __future__ import annotations

import os
import csv
import datetime as dt
from uuid import uuid4

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from .models import Base, Report, StoreStatus, BusinessHours, StoreTimeZone
from .schemas import TriggerResp, ReportStatusResp
from .ingestion import (
    get_engine, init_db,
    ingest_store_status, ingest_business_hours, ingest_store_timezones
)
from .report_logic import compute_store_metrics

# ----------------- Config via env -----------------
DB_URL     = os.environ.get("STOREMON_DB_URL", "sqlite:///storemon.db")
DATA_DIR   = os.environ.get("STOREMON_DATA_DIR", "sample_data")
REPORT_DIR = os.environ.get("STOREMON_REPORT_DIR", "reports")

app = FastAPI(title="Store Monitoring")

# ----------------- DB init -----------------
engine = get_engine(DB_URL)
init_db(engine)

def ensure_ingested_once() -> None:
    """If DB is empty, ingest from CSVs in DATA_DIR once."""
    with Session(engine) as sess:
        has_any = sess.execute(select(StoreStatus.id)).first()
        if has_any:
            return

    ss = os.path.join(DATA_DIR, "store_status.csv")
    bh = os.path.join(DATA_DIR, "business_hours.csv")      # menu_hours.csv -> business_hours.csv
    tz = os.path.join(DATA_DIR, "store_timezones.csv")     # timezones.csv  -> store_timezones.csv
    if not (os.path.exists(ss) and os.path.exists(bh) and os.path.exists(tz)):
        return

    ingest_store_status(ss, engine)
    ingest_business_hours(bh, engine)
    ingest_store_timezones(tz, engine)

# Call once at import-time (process start)
ensure_ingested_once()

# ----------------- Health endpoint -----------------
@app.get("/health")
def health():
    return {"ok": True}

# ----------------- Preview UI at "/" -----------------
@app.get("/", response_class=HTMLResponse)
def preview_home():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Store Monitoring — Preview</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:820px;margin:40px auto;padding:0 16px}
    .card{border:1px solid #e5e7eb;border-radius:12px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
    button{padding:10px 16px;border:0;border-radius:10px;cursor:pointer;font-weight:600;background:#111827;color:#fff}
    button[disabled]{opacity:.5;cursor:not-allowed}
    .muted{color:#6b7280}
    a.btn{display:inline-block;padding:10px 14px;border-radius:10px;background:#2563eb;color:#fff;text-decoration:none}
    .ok{color:#15803d;font-weight:700}
    .warn{color:#b45309;font-weight:700}
    code{background:#f3f4f6;padding:2px 6px;border-radius:6px}
  </style>
</head>
<body>
  <h1>Store Monitoring — Preview</h1>
  <p class="muted">Click “Generate Report”. We’ll create a report from <code>sample_data/</code>, poll status, then give you a download link. (Full OpenAPI docs at <a href="/docs" target="_blank">/docs</a>.)</p>

  <div class="card">
    <button id="genBtn">Generate Report</button>
    <span id="msg" class="muted" style="margin-left:10px;">Idle.</span>

    <div style="margin-top:10px;display:none" id="ridWrap">
      Report ID: <code id="rid"></code>
    </div>

    <div style="margin-top:8px;display:none" id="stWrap">
      Status: <span id="st" class="warn">Running</span>
    </div>

    <div style="margin-top:14px;display:none" id="dlWrap">
      <a id="dl" class="btn" href="#" download>Download CSV</a>
    </div>
  </div>

  <script>
    const $ = (id)=>document.getElementById(id);
    const genBtn = $("genBtn"), msg = $("msg"), ridWrap = $("ridWrap"),
          rid = $("rid"), stWrap = $("stWrap"), st = $("st"),
          dlWrap = $("dlWrap"), dl = $("dl");
    let timer = null;

    genBtn.onclick = async () => {
      genBtn.disabled = true; dlWrap.style.display = "none";
      stWrap.style.display = "none"; ridWrap.style.display = "none";
      msg.textContent = "Starting…";
      try {
        const r = await fetch("/trigger_report", {method:"POST"});
        if(!r.ok) throw new Error("trigger failed: "+r.status);
        const data = await r.json();
        rid.textContent = data.report_id;
        ridWrap.style.display = "block";
        msg.textContent = "Triggered. Polling status…";
        st.textContent = "Running"; st.className = "warn";
        stWrap.style.display = "block";
        poll(data.report_id);
      } catch (e) {
        msg.textContent = "Error: " + e.message;
        genBtn.disabled = false;
      }
    };

    async function poll(id){
      clearInterval(timer);
      timer = setInterval(async () => {
        try{
          const r = await fetch("/get_report?report_id="+encodeURIComponent(id));
          if(!r.ok) throw new Error("status failed: "+r.status);
          const s = await r.json();
          st.textContent = s.status;
          if(s.status === "Complete"){
            st.className = "ok";
            clearInterval(timer);
            const url = "/download_report?report_id="+encodeURIComponent(id);
            dl.href = url;
            dlWrap.style.display = "block";
            msg.textContent = "Done. Click “Download CSV”.";
            genBtn.disabled = false;
          }
        }catch(e){
          clearInterval(timer);
          msg.textContent = "Error: " + e.message;
          genBtn.disabled = false;
        }
      }, 1000);
    }
  </script>
</body>
</html>
    """

# ----------------- API endpoints -----------------
@app.post("/trigger_report", response_model=TriggerResp)
def trigger_report():
    report_id = str(uuid4())
    created_at = dt.datetime.now(dt.timezone.utc)
    with Session(engine) as sess, sess.begin():
        r = Report(report_id=report_id, status="Running", created_at=created_at)
        sess.add(r)

    try:
        path = run_report(report_id)
        with Session(engine) as sess, sess.begin():
            r = sess.execute(select(Report).where(Report.report_id == report_id)).scalar_one()
            r.status = "Complete"
            r.finished_at = dt.datetime.now(dt.timezone.utc)
            r.path = path
    except Exception as e:
        with Session(engine) as sess, sess.begin():
            r = sess.execute(select(Report).where(Report.report_id == report_id)).scalar_one()
            r.status = f"Error: {e}"
        raise

    return TriggerResp(report_id=report_id)

@app.get("/get_report", response_model=ReportStatusResp)
def get_report(report_id: str = Query(...)):
    with Session(engine) as sess:
        r = sess.execute(select(Report).where(Report.report_id == report_id)).scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="report_id not found")
        if r.status != "Complete":
            return ReportStatusResp(status=r.status)
        filename = os.path.basename(r.path or "")
        return ReportStatusResp(status="Complete", report_path=r.path, download_name=filename)

@app.get("/download_report")
def download_report(report_id: str = Query(...)):
    with Session(engine) as sess:
        r = sess.execute(select(Report).where(Report.report_id == report_id)).scalar_one_or_none()
        if not r or r.status != "Complete" or not r.path or not os.path.exists(r.path):
            raise HTTPException(status_code=404, detail="report not ready")
        return FileResponse(r.path, media_type="text/csv", filename=os.path.basename(r.path))

# ----------------- Report generator -----------------
def run_report(report_id: str) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    out_path = os.path.join(REPORT_DIR, f"{report_id}.csv")

    rows = []
    with Session(engine) as sess:
        store_ids = set(i[0] for i in sess.execute(select(StoreStatus.store_id).distinct()).all())
        store_ids |= set(i[0] for i in sess.execute(select(BusinessHours.store_id).distinct()).all())
        store_ids |= set(i[0] for i in sess.execute(select(StoreTimeZone.store_id).distinct()).all())

        for sid in sorted(store_ids, key=lambda x: str(x)):
            metrics = compute_store_metrics(sess, sid)
            rows.append(metrics)

    cols = [
        "store_id",
        "uptime_last_hour_minutes", "uptime_last_day_hours", "uptime_last_week_hours",
        "downtime_last_hour_minutes", "downtime_last_day_hours", "downtime_last_week_hours",
    ]

    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, 0) for k in cols})

    return out_path
