from __future__ import annotations
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from .models import Base, StoreStatus, BusinessHours, StoreTimeZone

def get_engine(db_path: str = "sqlite:///storemon.db"):
    return create_engine(db_path, future=True)

def init_db(engine):
    Base.metadata.create_all(engine)

def ingest_store_status(csv_path: str, engine):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["status"] = df["status"].str.lower().str.strip()
    with Session(engine) as sess, sess.begin():
        for row in df.itertuples(index=False):
            sess.add(StoreStatus(
                store_id=str(getattr(row, "store_id")),
                timestamp_utc=getattr(row, "timestamp_utc").to_pydatetime(),
                status=str(getattr(row, "status"))
            ))

def ingest_business_hours(csv_path: str, engine):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    with Session(engine) as sess, sess.begin():
        for row in df.itertuples(index=False):
            sess.add(BusinessHours(
                store_id=str(getattr(row, "store_id")),
                day_of_week=int(getattr(row, "dayOfWeek")),
                start_time_local=str(getattr(row, "start_time_local")),
                end_time_local=str(getattr(row, "end_time_local")),
            ))

def ingest_store_timezones(csv_path: str, engine):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    with Session(engine) as sess, sess.begin():
        for row in df.itertuples(index=False):
            sess.add(StoreTimeZone(
                store_id=str(getattr(row, "store_id")),
                timezone_str=str(getattr(row, "timezone_str")),
            ))
