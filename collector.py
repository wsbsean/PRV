import json, os, statistics, urllib.request, datetime as dt, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
FEED_BASE = "https://www.trumpstruth.org/feed?limit=500"
UTC = dt.timezone.utc
HISTORY_DAYS = 90

def get_et_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("America/New_York")
        except Exception:
            pass
    # Fallback US Eastern TzInfo supporting EST (-5) and EDT (-4)
    class USEastern(dt.tzinfo):
        def utcoffset(self, d):
            return dt.timedelta(hours=-4 if self._is_dst(d) else -5)
        def dst(self, d):
            return dt.timedelta(hours=1 if self._is_dst(d) else 0)
        def tzname(self, d):
            return "EDT" if self._is_dst(d) else "EST"
        def _is_dst(self, d):
            if d is None or d.year < 2007:
                return False
            # 2nd Sunday in March at 2am to 1st Sunday in November at 2am
            mar1 = dt.datetime(d.year, 3, 1)
            dst_start = mar1 + dt.timedelta(days=(6 - mar1.weekday()) % 7 + 7, hours=2)
            nov1 = dt.datetime(d.year, 11, 1)
            dst_end = nov1 + dt.timedelta(days=(6 - nov1.weekday()) % 7, hours=2)
            naive = d.replace(tzinfo=None)
            return dst_start <= naive < dst_end
    return USEastern()

ET_TZ = get_et_tz()

def now_et():
    return dt.datetime.now(UTC).astimezone(ET_TZ)

def fetch(end_date=None):
    url = FEED_BASE + (f"&end_date={end_date}" if end_date else "")
    req = urllib.request.Request(url, headers={"User-Agent": "PostPulse/1.0 public-monitor"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def parse(xml):
    root = ET.fromstring(xml)
    out = []
    for item in root.findall(".//item"):
        d = item.findtext("pubDate")
        link = (item.findtext("link") or "").strip()
        if not d:
            continue
        try:
            t_et = parsedate_to_datetime(d).astimezone(ET_TZ)
        except Exception:
            continue
        out.append({
            "id": link or d,
            "timestamp": t_et.isoformat(),
            "date_et": t_et.strftime("%Y-%m-%d"),
            "url": link
        })
    return out

def load():
    p = os.path.join(DATA, "posts.json")
    try:
        items = json.load(open(p, encoding="utf8"))
        for x in items:
            t_et = dt.datetime.fromisoformat(x["timestamp"]).astimezone(ET_TZ)
            x["timestamp"] = t_et.isoformat()
            x["date_et"] = t_et.strftime("%Y-%m-%d")
        return items
    except Exception:
        return []

def save(x):
    json.dump(x, open(os.path.join(DATA, "posts.json"), "w", encoding="utf8"), indent=2)

def backfill_and_merge(existing, target_days=95):
    by_id = {x["id"]: x for x in existing}
    # Always fetch latest posts first
    try:
        latest = parse(fetch())
        for x in latest:
            by_id[x["id"]] = x
    except Exception as e:
        print("Feed error (latest):", e)

    cutoff_target = now_et() - dt.timedelta(days=target_days)
    # Page backwards using end_date if history does not yet cover target_days
    for _ in range(20):
        if not by_id:
            break
        oldest_ts = min(dt.datetime.fromisoformat(x["timestamp"]).astimezone(ET_TZ) for x in by_id.values())
        if oldest_ts <= cutoff_target:
            break
        end_date_str = oldest_ts.strftime("%Y-%m-%d")
        try:
            older = parse(fetch(end_date=end_date_str))
        except Exception as e:
            print(f"Feed error (end_date={end_date_str}):", e)
            break
        if not older:
            break
        before_count = len(by_id)
        for x in older:
            by_id[x["id"]] = x
        new_oldest = min(dt.datetime.fromisoformat(x["timestamp"]).astimezone(ET_TZ) for x in by_id.values())
        if len(by_id) == before_count or new_oldest >= oldest_ts:
            # Step back one calendar day if a single day had >500 posts or no older items returned
            prev_day = (oldest_ts - dt.timedelta(days=1)).strftime("%Y-%m-%d")
            try:
                older2 = parse(fetch(end_date=prev_day))
                for x in older2:
                    by_id[x["id"]] = x
                if len(by_id) == before_count:
                    break
            except Exception:
                break

    posts = sorted(by_id.values(), key=lambda x: x["timestamp"])
    # Keep two years locally
    cutoff_keep = (now_et() - dt.timedelta(days=730)).isoformat()
    return [x for x in posts if dt.datetime.fromisoformat(x["timestamp"]).isoformat() >= cutoff_keep]

def calc(posts):
    t = now_et()
    ts_list = sorted(dt.datetime.fromisoformat(x["timestamp"]).astimezone(ET_TZ) for x in posts)

    def count_ts(start, end):
        # Binary search or fast comprehension over sorted timestamps
        return sum(start <= x < end for x in ts_list)

    today_start = t.replace(hour=0, minute=0, second=0, microsecond=0)
    earliest_ts = ts_list[0] if ts_list else t
    earliest_day = earliest_ts.replace(hour=0, minute=0, second=0, microsecond=0)
    avail_days = max(1, min(HISTORY_DAYS, (today_start - earliest_day).days))

    # 1. Full-day counts over the prior `avail_days` completed calendar days (in US Eastern Time)
    daily_counts = []
    for d in range(1, avail_days + 1):
        day_end = today_start - dt.timedelta(days=d - 1)
        day_start = today_start - dt.timedelta(days=d)
        daily_counts.append(count_ts(day_start, day_end))

    avg_day = statistics.mean(daily_counts) if daily_counts else 0.0
    avg_week = avg_day * 7.0
    avg_12h = avg_day / 2.0
    avg_6h = avg_day / 4.0
    avg_hour = avg_day / 24.0

    base = {
        "avg_day": avg_day,
        "avg_week": avg_week,
        "avg_12h": avg_12h,
        "avg_6h": avg_6h,
        "avg_hour": avg_hour
    }

    # Helper: average count for the exact same time-of-day window across the prior `avail_days` days
    def same_time_window_baseline(win_start, win_end):
        vals = []
        for d in range(1, avail_days + 1):
            s = win_start - dt.timedelta(days=d)
            e = win_end - dt.timedelta(days=d)
            vals.append(count_ts(s, e))
        return statistics.mean(vals) if vals else 0.0

    # Summary cards:
    # - "12h": Last 12 hours vs historical average for the same 12-hour time-of-day window
    # - "24h" ("Today" card): Posts since 12:00 AM ET today vs historical average from 12:00 AM ET to current time-of-day
    # - "7d" ("This week" card): Posts in last 7 days vs 90-day weekly average
    c_12h = count_ts(t - dt.timedelta(hours=12), t)
    b_12h = same_time_window_baseline(t - dt.timedelta(hours=12), t)

    c_today = count_ts(today_start, t)
    b_today_so_far = same_time_window_baseline(today_start, t)

    c_7d = count_ts(t - dt.timedelta(days=7), t)
    b_7d = avg_week

    summary = {
        "12h": {
            "current": c_12h,
            "baseline": b_12h,
            "pct": ((c_12h - b_12h) / b_12h * 100.0 if b_12h else 0.0)
        },
        "24h": {
            "current": c_today,
            "baseline": b_today_so_far,
            "full_day_baseline": avg_day,
            "pct": ((c_today - b_today_so_far) / b_today_so_far * 100.0 if b_today_so_far else 0.0)
        },
        "7d": {
            "current": c_7d,
            "baseline": b_7d,
            "pct": ((c_7d - b_7d) / b_7d * 100.0 if b_7d else 0.0)
        }
    }

    # Chart series for each range button
    series = {}
    for key, hours in [("1h", 1), ("6h", 6), ("12h", 12), ("24h", 24), ("3d", 72), ("7d", 168), ("30d", 720), ("90d", 2160)]:
        arr = []
        if key == "24h":
            # Show last 30 calendar days in US Eastern Time (including Today at the right edge)
            for i in range(29, -1, -1):
                d_start = today_start - dt.timedelta(days=i)
                d_end = t if i == 0 else d_start + dt.timedelta(days=1)
                c = count_ts(d_start, d_end)
                b = b_today_so_far if i == 0 else avg_day
                arr.append({"current": c, "baseline": round(b, 2), "label": d_start.strftime("%b %d")})
        elif hours < 24:
            # Sub-day buckets: compare each bucket against its matching time-of-day average over the past 90 days
            step = dt.timedelta(hours=hours)
            n = 24
            anchor = t.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
            for i in range(n - 1, -1, -1):
                e = min(t, anchor - dt.timedelta(hours=i * hours))
                a = anchor - dt.timedelta(hours=(i + 1) * hours)
                c = count_ts(a, e)
                b = same_time_window_baseline(a, e)
                arr.append({"current": c, "baseline": round(b, 2), "label": a.strftime("%I:%M %p ET")})
        else:
            # Multi-day buckets (3d, 7d, 30d, 90d)
            days_per_bin = {"3d": 1, "7d": 1, "30d": 1, "90d": 3}[key]
            num_bins = {"3d": 3, "7d": 7, "30d": 30, "90d": 30}[key]
            for i in range(num_bins - 1, -1, -1):
                d_start = today_start - dt.timedelta(days=i * days_per_bin)
                d_end = t if i == 0 else d_start + dt.timedelta(days=days_per_bin)
                c = count_ts(d_start, d_end)
                b = (avg_day * (days_per_bin - 1) + b_today_so_far) if i == 0 else (avg_day * days_per_bin)
                arr.append({"current": c, "baseline": round(b, 2), "label": d_start.strftime("%b %d")})
        series[key] = arr

    alerts = []
    for k, label_name in [("12h", "Last 12h"), ("24h", "Today (so far)"), ("7d", "Last 7d")]:
        s = summary[k]
        low = s["baseline"] * 0.5
        high = s["baseline"] * 1.5
        if s["current"] > high:
            alerts.append({"label": "HIGH ACTIVITY", "level": "high", "window": label_name, "current": s["current"], "low": round(low, 1), "high": round(high, 1), "pct": s["pct"]})
        elif s["current"] < low:
            alerts.append({"label": "LOW ACTIVITY", "level": "low", "window": label_name, "current": s["current"], "low": round(low, 1), "high": round(high, 1), "pct": s["pct"]})

    unique_days = len({x["date_et"] for x in posts})
    return {
        "generated_at": t.isoformat(),
        "timezone": "America/New_York (ET)",
        "account": {"name": "Donald Trump", "handle": "realDonaldTrump", "platform_label": "Truth Social"},
        "history_days": avail_days,
        "total_days_collected": unique_days,
        "total_posts": len(posts),
        "baseline": base,
        "summary": summary,
        "series": series,
        "alerts": alerts
    }

def main():
    posts = load()
    posts = backfill_and_merge(posts, target_days=95)
    save(posts)
    stats = calc(posts)
    json.dump(stats, open(os.path.join(DATA, "statistics.json"), "w", encoding="utf8"), indent=2)

if __name__ == "__main__":
    main()

