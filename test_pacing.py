"""Synthetic pacing seeds: early window (UNDER at high %), late window (AHEAD
at moderate %), exact-pace edges, unknown-span quota."""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _pacing  # noqa

DAY, WEEK = 86400, 7 * 86400
MS = lambda dt: dt.timestamp() * 1000


def run(span, reset, now, pct, expect):
    out = _pacing(pct, MS(reset) if isinstance(reset, datetime) else reset, span,
                  now=now.timestamp())
    print(f"span={span} reset={reset} now={now} pct={pct} -> {out!r}")
    assert out, "no verdict"
    if expect == "UNDER":
        assert out.startswith("-"), out
    elif expect == "AHEAD":
        assert out.startswith("+") and out != "+0%", out
    else:
        assert out == "+0%", out
    return out


# --- daily: window = reset - 24h ------------------------------------------
D = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
dstart = D - timedelta(days=1)
run(DAY, D, dstart + timedelta(hours=6), 5, "UNDER")     # 25% elapsed, 5%
run(DAY, D, dstart + timedelta(hours=6), 80, "AHEAD")    # 25% elapsed, 80%
run(DAY, D, D - timedelta(hours=1), 100, "AHEAD")        # 96% elapsed, 100%
assert _pacing(50, MS(D), DAY, now=(dstart + timedelta(hours=12)).timestamp()) == "+0%"

# --- weekly: window = reset - 7d, any weekday/wall-clock -------------------
W = datetime(2026, 9, 30, 19, 53, 39, tzinfo=timezone.utc)   # Wednesday
wstart = W - timedelta(days=7)
assert _pacing(50, MS(W), WEEK, now=(wstart + (W - wstart) / 2).timestamp()) == "+0%"
run(WEEK, W, wstart + timedelta(days=1), 5, "UNDER")          # 14% elapsed
run(WEEK, W, wstart + timedelta(days=1), 80, "AHEAD")
run(WEEK, W, W - timedelta(hours=6), 100, "AHEAD")

# --- no window documented (token trial): never a verdict -------------------
assert _pacing(50, MS(W), None, now=wstart.timestamp()) == ""

# --- degenerate inputs -----------------------------------------------------
assert _pacing(None, MS(W), WEEK, now=wstart.timestamp()) == ""
assert _pacing(50, None, WEEK, now=wstart.timestamp()) == ""
assert _pacing(50, "not-a-number", WEEK, now=wstart.timestamp()) == ""

# --- OpenCode windows: ISO resetsAt, spans in seconds ----------------------
from __init__ import _pacing_iso  # noqa

FIVE_H, WEEK_S = 5 * 3600, 7 * 86400

def run_iso(span, resets_at, now, pct, expect):
    out = _pacing_iso(pct, resets_at, span=span, now=now)
    print(f"iso span={span} reset={resets_at} now={now} pct={pct} -> {out!r}")
    assert out, "no verdict"
    if expect == "UNDER":
        assert out.startswith("-"), out
    elif expect == "AHEAD":
        assert out.startswith("+") and out != "+0%", out
    else:
        assert out == "+0%", out
    return out

R = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)      # rolling 5h window
r0 = R - timedelta(hours=5)
assert _pacing_iso(40, R.strftime("%Y-%m-%dT%H:%M:%SZ"), span=FIVE_H,
                   now=r0 + timedelta(hours=2)) == "+0%"
run_iso(FIVE_H, R.strftime("%Y-%m-%dT%H:%M:%SZ"), r0 + timedelta(hours=1), 5, "UNDER")
run_iso(FIVE_H, R.strftime("%Y-%m-%dT%H:%M:%SZ"), R - timedelta(minutes=30), 95, "AHEAD")

W2 = datetime(2026, 9, 30, 19, 53, 39, tzinfo=timezone.utc)  # non-Monday reset
s2 = W2 - timedelta(days=7)
assert _pacing_iso(50, W2.strftime("%Y-%m-%dT%H:%M:%SZ"), span=WEEK_S,
                   now=s2 + (W2 - s2) / 2) == "+0%"
run_iso(WEEK_S, W2.strftime("%Y-%m-%dT%H:%M:%SZ"), s2 + timedelta(days=1), 5, "UNDER")
run_iso(WEEK_S, W2.strftime("%Y-%m-%dT%H:%M:%SZ"), W2 - timedelta(hours=6), 100, "AHEAD")

# monthly: span omitted -> the calendar month before reset
from __init__ import _one_month_like  # noqa

M = datetime(2026, 10, 14, 19, 53, 39, tzinfo=timezone.utc)
mstart = M - _one_month_like(M)                       # 2026-09-14 19:53 (30d span)
assert _pacing_iso(50, M.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   now=mstart + (M - mstart) / 2) == "+0%"
# short-month awareness: reset Mar 1 -> February window (28d, non-leap 2027)
assert _pacing_iso(50, "2027-03-01T00:00:00Z",
                   now=datetime(2027, 2, 15, 0, 0, tzinfo=timezone.utc)) == "+0%"
assert _pacing_iso(42, "garbage") == ""
assert _pacing_iso(42, "2026-09-30T19:53:39Z", span=-1) == ""

print("ALL PACING SEEDS PASS")
