"""Duplicate-footer regression: transform output carries exactly ONE footer block."""
import os
import sys
from datetime import datetime, timedelta, timezone

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

import __init__ as p

now = datetime.now(timezone.utc)
ms = lambda **kw: int(((now + timedelta(**kw)).timestamp()) * 1000)
LIVE = {
    "active": True,
    "state": "active",
    "dailyInputTokens": {"used": 6, "remaining": 94, "percentUsed": 0.06,
                         "resetAt": ms(hours=8)},
    "weeklyInputTokens": {"used": 7, "remaining": 93, "percentUsed": 0.07,
                          "resetAt": ms(days=3)},
}

ECHO_IDENTICAL = "Body.\n\n_NanoGPT: day 6% · wk 7%_\n\n_NanoGPT: day 6% · wk 7%_"
ECHO_STALE = "Body.\n\n_NanoGPT: day 5% · wk 7%_\n\n_NanoGPT: day 6% · wk 8%_"
ECHO_DEGENERATE = "Body.\n\n_NanoGPT: ...\n\nNanoGPT: day 6% · wk 7%"
ECHO_BOLD = "Body.\n\n**_NanoGPT: day 6% · wk 7%_**"
CLEAN = "Just a reply."
OPENCODE = "Go: 5h 6% · wk 7% · mo 42%"


def run(text, data=LIVE):
    p._state = {"data": data, "fetched_at": 0.0}
    p._fetch_usage = lambda: p._state.get("data")
    return p.transform_llm_output(text, model="m", platform="telegram", session_id="s")


def footers(text):
    return [ln for ln in text.split("\n") if p._is_footer_line(ln)]


def main():
    for name, sample in (("identical", ECHO_IDENTICAL), ("stale", ECHO_STALE),
                         ("degenerate", ECHO_DEGENERATE), ("bold", ECHO_BOLD),
                         ("clean", CLEAN)):
        out = run(sample)
        assert isinstance(out, str), f"{name}: returned {out!r}"
        assert len(footers(out)) == 1, f"{name}: {len(footers(out))} footers -> {out!r}"
        assert out.startswith(sample.split("\n")[0]), f"{name}: body lost -> {out!r}"
        print(f"{name}: 1 footer OK")

    once, twice = run(CLEAN), run(run(CLEAN))
    assert len(footers(twice)) == 1, f"not idempotent -> {twice!r}"
    last = footers(twice)[0].strip()
    assert not last.startswith(("*", "_")) and not last.endswith(("*", "_")), twice
    print("idempotent: 1 footer OK")

    out = run(ECHO_STALE)
    assert len(footers(out)) == 1 and not out.startswith("\n"), repr(out)
    print("leading-blank guard OK")

    out = run(ECHO_DEGENERATE, data=None)
    assert out == "Body.", f"expected cleaned body, got {out!r}"
    assert run(CLEAN, data=None) is None
    print("no-data: echoes stripped, clean text untouched OK")

    assert p.transform_llm_output(ECHO_STALE, platform="cli") is None
    assert p.transform_llm_output(None, platform="telegram") is None
    print("platform/empty guards OK")

    # echoes the guard used to miss: mangled labels, fractional %, backticks
    for echo in ("Body.\n\nday 1% · wk 11% (-62%) 1.9d",
                 "Body.\n\nday 9.5% · wk 11%",
                 "Body.\n\n`NanoGPT: day 0% · wk 11%`",
                 "Body.\n\n**_NanoGPT: day 6% · wk 7%_**"):
        out = run(echo)
        assert len(footers(out)) == 1 and echo.split("\n")[-1] not in out, repr(out)
    print("escaped echoes: stale footer stripped OK")

    # the opencode-usage plugin's rows are never swallowed by this one
    both = f"Body.\n\n{OPENCODE}"
    out = run(both)
    assert out.split("\n")[2] == OPENCODE, out
    assert len(footers(out)) == 1 and len(out.split("\n\n")) == 3, out
    print("opencode rows preserved OK")

    # append-only: a reply carrying no footer row is returned byte-identical
    # (the strip path also collapses blank lines — it must never run blind)
    for body in ("para one\n\n\n\npara two",
                 "text\n\n```\nx = 1\n\n\n\ny = 2\n```",
                 "day 1 of the challenge\n\nimg 2048x2048 upscale"):
        out = run(body)
        assert isinstance(out, str) and out.startswith(body), f"body mutated -> {out!r}"
        assert run(body, data=None) is None, f"no data, no footer, but changed -> {body!r}"
    print("append-only: footer-less replies untouched OK")

    print("ALL DEDUP CHECKS PASS")


if __name__ == "__main__":
    main()
