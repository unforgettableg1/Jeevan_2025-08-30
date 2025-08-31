from __future__ import annotations
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import datetime as dt
import pytz
from .models import StoreStatus, BusinessHours, StoreTimeZone
from .utils_time import Interval, local_business_intervals_utc

DEFAULT_TZ = "America/Chicago"

def _parse_hhmmss(s: str) -> dt.time:
    parts = [int(p) for p in s.split(":")]
    return dt.time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)

def get_now(sess: Session) -> dt.datetime:
    max_ts = sess.execute(select(func.max(StoreStatus.timestamp_utc))).scalar_one_or_none()
    if max_ts is None:
        return dt.datetime.now(dt.timezone.utc)
    return max_ts.astimezone(dt.timezone.utc)

def get_store_timezone(sess: Session, store_id: str):
    tz = sess.execute(
        select(StoreTimeZone.timezone_str).where(StoreTimeZone.store_id == store_id)
    ).scalar_one_or_none()
    if not tz:
        tz = DEFAULT_TZ
    return pytz.timezone(tz)

def get_business_hours(sess: Session, store_id: str) -> List[Tuple[int, dt.time, dt.time]]:
    recs = sess.execute(
        select(BusinessHours.day_of_week, BusinessHours.start_time_local, BusinessHours.end_time_local)
        .where(BusinessHours.store_id == store_id)
    ).all()
    if not recs:
        return [(dow, dt.time(0,0,0), dt.time(0,0,0)) for dow in range(7)]
    return [(dow, _parse_hhmmss(s), _parse_hhmmss(e)) for dow, s, e in recs]

def window_ranges(now: dt.datetime):
    return {
        "last_hour": (now - dt.timedelta(hours=1), now),
        "last_day":  (now - dt.timedelta(days=1), now),
        "last_week": (now - dt.timedelta(days=7), now),
    }

def fetch_status_points(sess: Session, store_id: str, start: dt.datetime, end: dt.datetime):
    q = (
        select(StoreStatus.timestamp_utc, StoreStatus.status)
        .where(StoreStatus.store_id == store_id)
        .where(StoreStatus.timestamp_utc <= end)
        .order_by(StoreStatus.timestamp_utc.asc())
    )
    points = [(ts.astimezone(dt.timezone.utc), status) for ts, status in sess.execute(q).all()]
    return points

def interpolate_segments(points, start: dt.datetime, end: dt.datetime):
    if start >= end:
        return []
    prior = None
    for ts, st in points:
        if ts <= start:
            prior = (ts, st)
        else:
            break
    if prior is None:
        future = next((p for p in points if p[0] >= start), None)
        base_status = future[1] if future else "inactive"
    else:
        base_status = prior[1]

    segs = []
    cur_t = start
    cur_status = base_status
    for ts, st in points:
        if ts <= start:
            continue
        if ts >= end:
            break
        if ts > cur_t:
            segs.append((Interval(cur_t, ts), cur_status))
            cur_t = ts
            cur_status = st
        else:
            cur_status = st
    if cur_t < end:
        segs.append((Interval(cur_t, end), cur_status))
    return segs

def business_intervals_utc_for_range(store_id: str, sess: Session, start: dt.datetime, end: dt.datetime):
    tz = get_store_timezone(sess, store_id)
    rules = get_business_hours(sess, store_id)
    out = []
    cur_local_date = start.astimezone(tz).date()
    end_local_date = (end - dt.timedelta(seconds=1)).astimezone(tz).date()
    while cur_local_date <= end_local_date:
        out.extend(local_business_intervals_utc(cur_local_date, rules, tz))
        cur_local_date += dt.timedelta(days=1)
    filtered = []
    window = Interval(start, end)
    for iv in out:
        inter = iv.intersect(window)
        if inter:
            filtered.append(inter)
    return filtered

def sum_overlap(segs, biz_intervals):
    up = 0.0
    down = 0.0
    for b in biz_intervals:
        for seg, st in segs:
            inter = seg.intersect(b)
            if not inter:
                continue
            dur = inter.duration_seconds()
            if st == "active":
                up += dur
            else:
                down += dur
    return up, down

def compute_store_metrics(sess: Session, store_id: str):
    now = get_now(sess)
    windows = window_ranges(now)
    results = {"store_id": store_id}
    points = fetch_status_points(sess, store_id, min(w[0] for w in windows.values()), now)

    for key, (ws, we) in windows.items():
        segs = interpolate_segments(points, ws, we)
        biz = business_intervals_utc_for_range(store_id, sess, ws, we)
        up_s, down_s = sum_overlap(segs, biz)

        if key == "last_hour":
            results["uptime_last_hour_minutes"] = round(up_s / 60.0, 2)
            results["downtime_last_hour_minutes"] = round(down_s / 60.0, 2)
        else:
            results[f"uptime_{key}_hours"] = round(up_s / 3600.0, 2)
            results[f"downtime_{key}_hours"] = round(down_s / 3600.0, 2)

    return results
