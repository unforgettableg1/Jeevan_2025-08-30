from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import datetime as dt
import pytz

WEEKDAYS = list(range(7))  # 0=Monday ... 6=Sunday

@dataclass(frozen=True)
class Interval:
    start: dt.datetime  # inclusive
    end: dt.datetime    # exclusive

    def duration_seconds(self) -> float:
        return max(0.0, (self.end - self.start).total_seconds())

    def intersect(self, other: "Interval") -> "Interval|None":
        s = max(self.start, other.start)
        e = min(self.end, other.end)
        if s >= e:
            return None
        return Interval(s, e)

def make_utc(dt_like: dt.datetime) -> dt.datetime:
    if dt_like.tzinfo is None:
        raise ValueError("Naive datetime not allowed")
    return dt_like.astimezone(dt.timezone.utc)

def local_business_intervals_utc(
    day: dt.date,
    biz_hours_local: List[Tuple[int, dt.time, dt.time]],
    tz: pytz.BaseTzInfo,
) -> List[Interval]:
    """
    For a given calendar date (day) and a list of business hours tuples
    (dayOfWeek, start_time_local, end_time_local), produce UTC intervals that
    fall on that date *in local time*.
    Handles cross-midnight by splitting into two dates.
    """
    out: List[Interval] = []
    local = tz

    for dow, start_t, end_t in biz_hours_local:
        if day.weekday() != dow:
            continue
        # Construct start/end in local tz for this 'day'
        start_local = local.localize(dt.datetime.combine(day, start_t))
        end_local = local.localize(dt.datetime.combine(day, end_t))

        if end_t <= start_t:
            # Crosses midnight -> split into [start, day_end) and [day_start_next, end_next)
            end_of_day_local = local.localize(dt.datetime.combine(day, dt.time(23, 59, 59, 999999)))
            start_of_next_local = local.localize(dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 0)))
            first = (start_local, end_of_day_local + dt.timedelta(microseconds=1))
            second = (start_of_next_local, end_local + dt.timedelta(days=1))
            parts = [first, second]
        else:
            parts = [(start_local, end_local)]

        for s_local, e_local in parts:
            s_utc = s_local.astimezone(dt.timezone.utc)
            e_utc = e_local.astimezone(dt.timezone.utc)
            out.append(Interval(s_utc, e_utc))

    return out

def split_into_days_utc(start: dt.datetime, end: dt.datetime) -> List[Interval]:
    """
    Split [start, end) into day-sized UTC buckets (midnight boundaries in UTC).
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Expect timezone-aware datetimes")

    out: List[Interval] = []
    cur = start
    while cur < end:
        next_midnight = (cur + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        next_midnight = next_midnight.astimezone(dt.timezone.utc)
        stop = min(end, next_midnight)
        out.append(Interval(cur, stop))
        cur = stop
    return out
