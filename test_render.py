"""Pure renderer ladder: L0 single line -> L1 first-reset drop -> one line per
quota. Inputs are segment tuples, outputs exact strings."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _BUDGET, _compact_time, _is_footer_line, _render_footer, _resets_in  # noqa

NORMAL = [
    ("day", "6", "", "3.2h"),
    ("wk", "7", "+12%", "3.2d"),    # 7% < 10% -> pace suppressed at render
    ("img", "42", "-8%", "20.2d"),
]
L0 = "NanoGPT: day 6% 3.2h · wk 7% 3.2d · img 42% (-8%) 20.2d"
L1 = "NanoGPT: day 6% · wk 7% 3.2d · img 42% (-8%) 20.2d"

out = _render_footer(NORMAL)
assert out == L1, out
assert len(L0) == 55 and len(out) == 50 <= _BUDGET, (len(L0), len(out))

out = _render_footer(NORMAL, budget=49)
assert out == "NanoGPT: day 6% 3.2h\nNanoGPT: wk 7% 3.2d\nNanoGPT: img 42% (-8%) 20.2d", out
assert [len(r) for r in out.split("\n")] == [20, 19, 28]

# single quota fits one line; empty input renders empty
assert _render_footer([("day", "25", "", "3.2h")]) == "NanoGPT: day 25% 3.2h"
assert _render_footer([]) == ""

# unknown (degraded) quota renders '?', never 0
assert _render_footer([("day", "?", "", "")]) == "NanoGPT: day ?"

# pacing only once 10% of that period's usage is spent
assert _render_footer([("wk", "9", "+12%", "3.2d")]) == "NanoGPT: wk 9% 3.2d"
assert _render_footer([("wk", "10", "+12%", "3.2d")]) == "NanoGPT: wk 10% (+12%) 3.2d"

# absent fields are omitted
assert _render_footer([("wk", "41", "", "")]) == "NanoGPT: wk 41%"

# largest unit only
assert _compact_time(4 * 3600 + 49 * 60) == "4.8h"
assert _compact_time(2 * 86400 + 3 * 3600) == "2.1d"
assert _compact_time(18 * 86400 + 23 * 3600) == "19d"
assert _compact_time(45 * 60) == "45m"

# resetAt is epoch milliseconds: past -> 'now', absent/invalid -> omitted
assert _resets_in(1_600_000_000_000) == "now"
assert _resets_in(None) == "" and _resets_in("garbage") == "" and _resets_in(0) == ""

# matcher recognizes our rows and NEVER the opencode-usage plugin's shapes
for row in (L0, L1, "NanoGPT: day 6% 3.2h", "NanoGPT: wk 7% 3.2d",
            "day 25% · wk 25%", "NanoGPT: day ?", "day ? · wk 7%",
            "**_NanoGPT: day 25% · wk 25%_**"):
    assert _is_footer_line(row), row
for other in ("Just a reply.", "Go buy milk", "Go: 5h 6% · wk 7% · mo 42%",
              "wk 7% 1.3d", "5h 6% 1.1h", "mo 42% 20d"):
    assert not _is_footer_line(other), other

# end-to-end from a documented payload shape (percentUsed is a fraction)
import __init__ as p
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
ms = lambda **kw: int(((now + timedelta(**kw)).timestamp()) * 1000)
p._state = {"data": {
    "dailyInputTokens": {"used": 1000, "remaining": 0, "percentUsed": 1.0,
                         "resetAt": ms(hours=4, minutes=59, seconds=59)},
    "weeklyInputTokens": {"used": 1000, "remaining": 0, "percentUsed": 1.0,
                          "resetAt": ms(days=6, hours=23, minutes=30)},
    "dailyImages": {"used": 5, "remaining": 5, "percentUsed": 0.5,
                    "resetAt": ms(hours=3)},
}, "fetched_at": 0.0}
p._fetch_usage = lambda: p._state.get("data")

# pacing is skipped when resetAt sits beyond the assumed window length
assert p._pacing(50, ms(days=30), 86400, now=now.timestamp()) == ""

out = p.transform_llm_output("Body text.", platform="telegram")
rows = out.split("\n\n", 1)[1].split("\n")
assert len(rows) == 3, out
assert rows[0] == "NanoGPT: day 100% (+21%) 5.0h", rows[0]
assert rows[1] == "NanoGPT: wk 100% (+100%) 7d", rows[1]
assert rows[2] == "NanoGPT: img 50% (-38%) 3.0h", rows[2]
assert all(len(r) <= _BUDGET for r in rows), rows

# transforming that footer again keeps the body and re-emits exactly one block
twice = p.transform_llm_output(out, platform="telegram")
assert twice.startswith("Body text."), twice
assert len([l for l in twice.split("\n") if p._is_footer_line(l)]) == 3, twice

# degraded window -> '?'; unconfigured window -> omitted entirely
segs = p._segments({"dailyInputTokens": {"percentUsed": None, "degraded": True,
                                         "resetAt": ms(hours=3)},
                    "weeklyInputTokens": None})
assert segs[0][1] == "?" and len(segs) == 1, segs

print("ALL RENDER CHECKS PASS")
