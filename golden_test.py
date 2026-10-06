"""Footer format determinism — golden snapshot test (no network).

Renders are byte-identical across consecutive runs: the payload is frozen
(past resetAt, sub-10% usage so pacing never renders) and the template lives
in exactly one place (_FOOTER_MD).
"""
import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PLUGIN_DIR)

LIVE_SHAPE = {
    "active": True,
    "state": "active",
    "dailyInputTokens": {"used": 1, "remaining": 99, "percentUsed": 0.01,
                         "resetAt": 1_700_000_000_000},
    "weeklyInputTokens": {"used": 5, "remaining": 95, "percentUsed": 0.05,
                          "resetAt": 1_700_000_000_000},
}


def run(plugin, data):
    plugin._state = {"data": data, "fetched_at": 0.0}
    plugin._fetch_usage = lambda: plugin._state.get("data")
    return plugin.transform_llm_output("Body text.", model="m", platform="telegram", session_id="s")


def golden():
    import __init__ as p
    out, out2 = run(p, LIVE_SHAPE), run(p, LIVE_SHAPE)
    assert isinstance(out, str) and out == out2, "consecutive runs differ!"
    assert out.encode() == out2.encode(), "not byte-identical"
    return out


def content_differs():
    import __init__ as p
    a = run(p, LIVE_SHAPE)
    import copy
    changed = copy.deepcopy(LIVE_SHAPE)
    changed["weeklyInputTokens"]["percentUsed"] = 0.06
    b = run(p, changed)
    assert a != b, "content change should change footer"
    return True


def wrapper_invariant():
    src = open(PLUGIN_DIR + "/__init__.py").read()
    assert src.count('_FOOTER_MD = "{line}"') == 1, "footer wrapper must be a single template constant"
    assert src.count("_FOOTER_MD.format(") == 2, "both emit sites must render the one template"
    assert "*{line}*" not in src and "_{line}_" not in src, "italic wrapper reintroduced"
    return True


def no_emphasis_wrapper():
    g = golden()
    assert "*" not in g, f"asterisk leaked: {g!r}"
    inner = g.rsplit("\n\n", 1)[1]
    assert not inner.startswith("_") and not inner.endswith("_"), f"underscore wrapper leaked: {inner!r}"
    return True


if __name__ == "__main__":
    g = golden()
    print("GOLDEN:", g)
    assert content_differs() and wrapper_invariant() and no_emphasis_wrapper()
    print("ALL GOLDEN CHECKS PASS")
