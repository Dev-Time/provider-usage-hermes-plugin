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

print("ALL PACING SEEDS PASS")
