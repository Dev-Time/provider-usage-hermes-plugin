"""Render ladders for BOTH providers, the shared matcher, and end-to-end
payload handling. Inputs are segment tuples, outputs exact strings."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import (_BUDGET, _compact_time, _is_footer_line, _one_month_like,
                      _pacing_iso, _render_footer, _resets_iso, _resets_ms)  # noqa

NANO = "NanoGPT: "
NORMAL = [
    ("day", "6", "", "3.2h"),
    ("wk", "7", "+12%", "3.2d"),    # 7% < 10% -> pace suppressed at render
    ("img", "42", "-8%", "20.2d"),
]
L0 = "NanoGPT: day 6% 3.2h · wk 7% 3.2d · img 42% (-8%) 20.2d"
L1 = "NanoGPT: day 6% · wk 7% 3.2d · img 42% (-8%) 20.2d"

assert _render_footer(NORMAL, lead=NANO) == L1, _render_footer(NORMAL, lead=NANO)
assert len(L0) == 55 and len(L1) == 50 <= _BUDGET
out = _render_footer(NORMAL, budget=49, lead=NANO)
assert out == "NanoGPT: day 6% 3.2h\nNanoGPT: wk 7% 3.2d\nNanoGPT: img 42% (-8%) 20.2d", out

# OpenCode ladder: no lead on L0/L1 (matches the live footer), "Go: " on L2 rows
GO = [("5h", "6", "", "3.2h"), ("wk", "7", "+12%", "3.2d"), ("mo", "42", "-8%", "20.2d")]
assert _render_footer(GO, row="Go: ") == "5h 6% 3.2h · wk 7% 3.2d · mo 42% (-8%) 20.2d"
assert _render_footer(GO, budget=38, row="Go: ") == \
    "Go: 5h 6% 3.2h\nGo: wk 7% 3.2d\nGo: mo 42% (-8%) 20.2d"
WORST = [("5h", "100", "", "5.0h"), ("wk", "100", "+100%", "7d"), ("mo", "100", "+100%", "30d")]
assert _render_footer(WORST, row="Go: ") == "5h 100% · wk 100% (+100%) 7d · mo 100% (+100%) 30d"
assert len(_render_footer(WORST, row="Go: ")) == 50 == _BUDGET

# single quota, empty input, unknown (degraded) quota, absent fields
assert _render_footer([("day", "25", "", "3.2h")], lead=NANO) == "NanoGPT: day 25% 3.2h"
assert _render_footer([]) == "" and _render_footer([], lead=NANO) == ""
assert _render_footer([("day", "?", "", "")], lead=NANO) == "NanoGPT: day ?"
assert _render_footer([("wk", "41", "", "")], lead=NANO) == "NanoGPT: wk 41%"

# pacing renders only once 10% of that period's usage is spent
assert _render_footer([("wk", "9", "+12%", "3.2d")], lead=NANO) == "NanoGPT: wk 9% 3.2d"
assert _render_footer([("wk", "10", "+12%", "3.2d")], lead=NANO) == "NanoGPT: wk 10% (+12%) 3.2d"

# largest unit only
assert _compact_time(4 * 3600 + 49 * 60) == "4.8h"
assert _compact_time(2 * 86400 + 3 * 3600) == "2.1d"
assert _compact_time(18 * 86400 + 23 * 3600) == "19d"
assert _compact_time(45 * 60) == "45m"

# reset countdown: epoch ms (NanoGPT) and ISO (OpenCode)
assert _resets_ms(1_600_000_000_000) == "now"
assert _resets_ms(None) == "" and _resets_ms("garbage") == "" and _resets_ms(0) == ""
assert _resets_iso("2020-01-01T00:00:00Z") == "now"
assert _resets_iso("") == "" and _resets_iso("garbage") == ""

# OpenCode pacing: reset-anchored window, monthly = previous month's length
assert _pacing_iso(50, "2026-09-28T00:00:00Z", span=7 * 86400,
                   now=__import__("datetime").datetime(2026, 9, 24, 12, 0,
                                                       tzinfo=__import__("datetime").timezone.utc)) == "+0%"
assert _pacing_iso(50, "2027-03-01T00:00:00Z",
                   now=__import__("datetime").datetime(2027, 2, 15, 0, 0,
                                                       tzinfo=__import__("datetime").timezone.utc)) == "+0%"
assert _pacing_iso(42, "garbage") == "" and _pacing_iso(None, "2026-09-28T00:00:00Z") == ""
assert _one_month_like(__import__("datetime").datetime(2027, 3, 1, tzinfo=__import__("datetime").timezone.utc)).days == 28

# matcher: our two families, and never ordinary prose
for row in (L0, L1, "NanoGPT: day 6% 3.2h", "NanoGPT: wk 7% 3.2d",
            "day 25% · wk 25%", "NanoGPT: day ?", "day ? · wk 7%",
            "**_NanoGPT: day 25% · wk 25%_**",
            "5h 6% 1.1h · wk 7% 1.3d · mo 42% 20.2d",
            "Go: 5h 6% 1.1h", "wk 7% 1.3d", "mo 42% 20d",
            "_Go: 5h 6% · wk 7% · mo 42%_", "Go: ..."):
    assert _is_footer_line(row), row
for other in ("Just a reply.", "Go buy milk", "Go to the store",
              "day 1 of the challenge", "img 500 files scanned",
              "img 2048x2048 upscale", "day 30.", "tok 42 for later",
              "NanoGPT: the full name is ...", "NanoGPT: pricing changed today"):
    assert not _is_footer_line(other), other

# end-to-end: both providers render into one block, echoes dedup to one block
import __init__ as p
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
ms = lambda **kw: int(((now + timedelta(**kw)).timestamp()) * 1000)
iso = lambda **kw: (now + timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")

p._fetch_nano = lambda: {
    "dailyInputTokens": {"used": 1000, "remaining": 0, "percentUsed": 1.0,
                         "resetAt": ms(hours=4, minutes=59, seconds=59)},
    "weeklyInputTokens": {"used": 1000, "remaining": 0, "percentUsed": 1.0,
                          "resetAt": ms(days=6, hours=23, minutes=30)},
    "dailyImages": {"used": 5, "remaining": 5, "percentUsed": 0.5,
                    "resetAt": ms(hours=3)},
}
p._fetch_opencode = lambda: {"usage": {
    "rolling": {"percent": 6, "resetsAt": iso(hours=4)},
    "weekly": {"percent": 7, "resetsAt": iso(days=3)},
    "monthly": {"percent": 42, "resetsAt": iso(days=9)},
}}

out = p.transform_llm_output("Body text.", platform="telegram")
rows = out.split("\n\n", 1)[1].split("\n")
assert len(rows) == 4, out
assert rows[0] == "NanoGPT: day 100% (+21%) 5.0h", rows[0]
assert rows[1] == "NanoGPT: wk 100% (+100%) 7d", rows[1]
assert rows[2] == "NanoGPT: img 50% (-38%) 3.0h", rows[2]
assert rows[3].startswith("5h 6%") and "wk 7%" in rows[3] and "mo 42%" in rows[3], rows[3]
assert all(len(r) <= _BUDGET for r in rows), rows

twice = p.transform_llm_output(out, platform="telegram")
assert twice.startswith("Body text."), twice
assert len([l for l in twice.split("\n") if p._is_footer_line(l)]) == 4, twice

# degraded window -> '?'; unconfigured window omitted; one bad value tolerated
segs = p._nano_segments({"dailyInputTokens": {"percentUsed": None, "degraded": True,
                                              "resetAt": ms(hours=3)},
                         "weeklyInputTokens": None,
                         "monthly": {"percentUsed": "bogus"}})
assert segs[0][1] == "?" and len(segs) == 1, segs

# OpenCode payload with no windows -> that provider contributes no line
p._fetch_opencode = lambda: {"usage": {}}
assert p._usage_line().startswith("NanoGPT:"), p._usage_line()

print("ALL RENDER CHECKS PASS")
