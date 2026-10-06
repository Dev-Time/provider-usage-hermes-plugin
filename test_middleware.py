"""llm_request middleware: footers stripped from assistant history rows only."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import __init__ as p

FOOTER_A = "NanoGPT: day 42% (+11%) 2.6h"
FOOTER_B = "NanoGPT: wk 7% 1.3d"
OPENCODE = "Go: 5h 42% (+11%) 2.6h"


def mw(**kwargs):
    return p.strip_footers_from_request(**kwargs)


out = mw(request={"messages": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": f"answer\n\n{FOOTER_A}"},
    {"role": "user", "content": "next"},
]})
assert out is not None and out["source"] == "provider-usage" and out["reason"]
assert out["request"]["messages"][1]["content"] == "answer", out["request"]["messages"][1]
assert out["request"]["messages"][0] == {"role": "user", "content": "hi"}
assert out["request"]["messages"][2] == {"role": "user", "content": "next"}
print("assistant str strip OK")

out = mw(request={"messages": [
    {"role": "assistant", "content": f"body\n{FOOTER_A}\n{FOOTER_B}\nday 49% 11.1d"},
]})
assert out["request"]["messages"][0]["content"] == "body", out["request"]["messages"][0]
print("multi-row strip OK")

rows = [{"role": r, "content": FOOTER_A} for r in ("user", "system")] + \
       [{"role": "tool", "tool_call_id": "c1", "content": FOOTER_A}]
assert mw(request={"messages": rows}) is None
print("non-assistant rows untouched OK")

# both row families are ours to strip now
out = mw(request={"messages": [{"role": "assistant", "content": f"answer\n\n{OPENCODE}"}]})
assert out["request"]["messages"][0]["content"] == "answer", out
print("opencode rows stripped OK")

assert mw(request={"messages": [{"role": "assistant", "content": "para one\n\n\npara two"}]}) is None
print("clean rows byte-identical OK")

assert mw(request={"messages": [{"role": "assistant", "content": None}]}) is None
assert mw(request={"messages": [{"role": "assistant", "content": 42}]}) is None
assert mw(request={"messages": [{"role": "assistant"}]}) is None
assert mw(request={"messages": []}) is None
assert mw(request={}) is None
assert mw(request="not-a-dict") is None
assert mw() is None
print("degenerate inputs OK")

parts = [{"type": "text", "text": "lead"},
         {"type": "text", "text": f"tail\n\n{FOOTER_A}"},
         {"type": "image_url", "image_url": {"url": "x"}}]
out = mw(request={"messages": [{"role": "assistant", "content": parts}]})
got = out["request"]["messages"][0]["content"]
assert got[0] == parts[0] and got[2] == parts[2]
assert got[1]["text"] == "tail", got[1]
print("list-content text parts OK")

out = mw(request={"input": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": f"ok\n\n{FOOTER_A}"},
]})
assert out["request"]["input"][1]["content"] == "ok"
assert out["request"]["input"][0] == {"role": "user", "content": "hi"}
print("responses-api input OK")

original = {"messages": [{"role": "assistant", "content": f"answer\n\n{FOOTER_A}"}]}
snapshot = copy.deepcopy(original)
out = mw(request=original)
assert original == snapshot, "input request was mutated"
assert out["request"] is not original and out["request"]["messages"] is not original["messages"]
assert mw(request={"messages": [{"role": "assistant", "content": "clean"}]}) is None
assert mw(request=out["request"]) is None
print("immutability + idempotent OK")

out = mw(request={"messages": [
    {"role": "assistant", "content": f"calling\n\n{FOOTER_A}",
     "tool_calls": [{"id": "c1", "function": {"name": "f", "arguments": "{}"}}]},
]})
row = out["request"]["messages"][0]
assert row["content"] == "calling"
assert row["tool_calls"] == [{"id": "c1", "function": {"name": "f", "arguments": "{}"}}]
print("tool_calls preserved OK")

out = mw(request={"messages": [{"role": "assistant", "content": FOOTER_A}]})
assert out["request"]["messages"][0]["content"] == ""
print("footer-only -> empty string OK")


class _Ctx:
    def __init__(self):
        self.hooks, self.middleware = [], []

    def register_hook(self, name, cb):
        self.hooks.append((name, cb))

    def register_middleware(self, kind, cb):
        self.middleware.append((kind, cb))


ctx = _Ctx()
p.register(ctx)
assert ctx.hooks == [("transform_llm_output", p.transform_llm_output)]
assert ctx.middleware == [("llm_request", p.strip_footers_from_request)]
print("register() wiring OK")

print("ALL MIDDLEWARE CHECKS PASS")
