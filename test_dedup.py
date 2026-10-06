"""Duplicate-footer regression: one transform output carries exactly one footer
block (both providers), and reply content outside footers is never touched."""
import os
import sys
from datetime import datetime, timedelta, timezone

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

import __init__ as p

now = datetime.now(timezone.utc)
ms = lambda **kw: int(((now + timedelta(**kw)).timestamp()) * 1000)
iso = lambda **kw: (now + timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")

NANO = {
    "dailyInputTokens": {"used": 6, "remaining": 94, "percentUsed": 0.06,
                         "resetAt": ms(hours=8)},
    "weeklyInputTokens": {"used": 7, "remaining": 93, "percentUsed": 0.07,
                          "resetAt": ms(days=3)},
}
GO = {"usage": {
    "rolling": {"percent": 5, "resetsAt": iso(hours=1)},
    "weekly": {"percent": 8, "resetsAt": iso(days=3)},
    "monthly": {"percent": 55, "resetsAt": iso(days=9)},
}}

ECHO_NANO = "Body.\n\n_NanoGPT: day 6% · wk 7%_\n\n_NanoGPT: day 6% · wk 7%_"
ECHO_GO = "Body.\n\n_Go: 5h 5% · wk 8% · mo 54%_\n\n5h 4% · wk 8% · mo 55%"
ECHO_MIXED = "Body.\n\nGo: 5h 5% · wk 8%\nNanoGPT: day 6% · wk 7%\n\nGo: ..."
ECHO_BOLD = "Body.\n\n**_NanoGPT: day 6% · wk 7%_**"
CLEAN = "Just a reply."


def run(text, nano=NANO, go=GO):
    p._fetch_nano = lambda: nano
    p._fetch_opencode = lambda: go
    return p.transform_llm_output(text, model="m", platform="telegram", session_id="s")


def footers(text):
    return [ln for ln in text.split("\n") if p._is_footer_line(ln)]


def main():
    for name, sample in (("nano", ECHO_NANO), ("opencode", ECHO_GO),
                         ("mixed", ECHO_MIXED), ("bold", ECHO_BOLD),
                         ("clean", CLEAN)):
        out = run(sample)
        assert isinstance(out, str), f"{name}: returned {out!r}"
        # one block = one line per provider with data
        assert len(footers(out)) == 2, f"{name}: {len(footers(out))} rows -> {out!r}"
        assert out.startswith(sample.split("\n")[0]), f"{name}: body lost -> {out!r}"
        print(f"{name}: one 2-row block OK")

    once, twice = run(CLEAN), run(run(CLEAN))
    assert len(footers(twice)) == 2, f"not idempotent -> {twice!r}"
    for row in footers(twice):
        last = row.strip()
        assert not last.startswith(("*", "_")) and not last.endswith(("*", "_")), twice
    print("idempotent: one block OK")

    out = run(ECHO_GO)
    assert len(footers(out)) == 2 and not out.startswith("\n"), repr(out)
    print("leading-blank guard OK")

    out = run(ECHO_MIXED, nano=None, go=None)
    assert out == "Body.", f"expected cleaned body, got {out!r}"
    assert run(CLEAN, nano=None, go=None) is None
    print("no-data: echoes stripped, clean text untouched OK")

    assert p.transform_llm_output(ECHO_NANO, platform="cli") is None
    assert p.transform_llm_output(None, platform="telegram") is None
    print("platform/empty guards OK")

    for echo in ("Body.\n\nday 1% · wk 11% (-62%) 1.9d",
                 "Body.\n\nNanoGPT: day 0% · wk 11%",
                 "Body.\n\n**_Go: 5h 6% · wk 7% · mo 42%_**",
                 "Body.\n\n6h 1% · wk 11% · mo 44%"):
        out = run(echo)
        assert len(footers(out)) == 2 and echo.split("\n")[-1] not in out, repr(out)
    print("escaped echoes: stale rows stripped OK")

    # append-only: a reply carrying no footer row is returned byte-identical
    for body in ("para one\n\n\n\npara two",
                 "text\n\n```\nx = 1\n\n\n\ny = 2\n```",
                 "day 1 of the challenge\n\nimg 2048x2048 upscale"):
        out = run(body)
        assert isinstance(out, str) and out.startswith(body), f"body mutated -> {out!r}"
        assert run(body, nano=None, go=None) is None, f"changed with no data -> {body!r}"
    print("append-only: footer-less replies untouched OK")

    # one provider down: the other still renders, as a single-row block
    out = run(CLEAN, nano=None)
    assert len(footers(out)) == 1 and footers(out)[0].startswith("5h"), out
    out = run(CLEAN, go=None)
    assert len(footers(out)) == 1 and footers(out)[0].startswith("NanoGPT:"), out
    print("single-provider degradation OK")

    print("ALL DEDUP CHECKS PASS")


if __name__ == "__main__":
    main()
