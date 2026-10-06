"""Provider usage footer — appends NanoGPT and OpenCode Go subscription usage
to the final gateway message via transform_llm_output."""

import json
import logging
import os
import re
import time
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

NANO_USAGE_URL = "https://api.nano-gpt.com/api/subscription/v1/usage"
OPENCODE_USAGE_URL = "https://opencode.ai/zen/go/v1/usage"
_USER_AGENT = "hermes-agent/0.21 (provider-usage-plugin)"

_state = {
    "nano": {"data": None, "fetched_at": 0.0},
    "opencode": {"data": None, "fetched_at": 0.0},
}

# NanoGPT quota key -> (label, window seconds); span drives pacing only, resetAt
# drives the countdown. `tokens` (token trial) has no documented window: no pace.
_NANO_QUOTAS = (
    ("dailyInputTokens", "day", 86400),
    ("weeklyInputTokens", "wk", 7 * 86400),
    ("dailyImages", "img", 86400),
    ("tokens", "tok", None),
)
# OpenCode window key -> (label, window length); monthly derives its span from
# its own resetsAt (previous calendar month, 28-31 days).
_GO_WINDOWS = (("rolling", "5h"), ("weekly", "wk"), ("monthly", "mo"))
_GO_SPANS = {"rolling": 5 * 3600, "weekly": 7 * 86400}


def _ttl():
    try:
        return max(1.0, float(os.environ.get("USAGE_TTL_SECONDS")))
    except (TypeError, ValueError):
        return 120.0


def _nano_key():
    for name in ("NANOGPT_API_KEY", "HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY"):
        key = os.environ.get(name, "")
        if key:
            return key
    return _resolved_key("custom:nanogpt", "nano")


def _opencode_key():
    for name in ("OPENCODE_GO_API_KEY", "OPENCODE_ZEN_API_KEY"):
        key = os.environ.get(name, "")
        if key:
            return key
    return _resolved_key("opencode-go", "opencode")


def _resolved_key(requested, needle):
    """Runtime-provider fallback, guarded so one provider's key is never sent to
    another host (the resolver falls back to OpenRouter when the ask is absent)."""
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime = resolve_runtime_provider(requested=requested)
        if needle in str(runtime.get("provider") or "").lower():
            return str(runtime.get("api_key") or "").strip()
    except Exception:
        pass
    return ""


def _fetch(which, url, key_fn):
    # Cache first: the resolver must run at most once per TTL, not per message.
    state = _state[which]
    if state["data"] and time.monotonic() - state["fetched_at"] < _ttl():
        return state["data"]
    key = key_fn()
    if not key:
        return None
    try:
        req = Request(url, headers={"Authorization": f"Bearer {key}",
                                    "User-Agent": _USER_AGENT})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        state["data"] = data
        state["fetched_at"] = time.monotonic()
        return data
    except Exception as exc:
        logger.debug("%s usage fetch failed: %s", which, exc)
        return None


def _fetch_nano():
    return _fetch("nano", NANO_USAGE_URL, _nano_key)


def _fetch_opencode():
    return _fetch("opencode", OPENCODE_USAGE_URL, _opencode_key)


def _compact_time(seconds) -> str:
    if seconds >= 86400:
        days = round(seconds / 86400, 1)
        return f"{int(days)}d" if days == int(days) else f"{days}d"
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds // 60}m"


def _resets_ms(reset_at) -> str:
    """Countdown from resetAt (UNIX epoch milliseconds)."""
    if not isinstance(reset_at, (int, float)) or reset_at <= 0:
        return ""
    seconds = int(reset_at / 1000 - time.time())
    return "now" if seconds <= 0 else _compact_time(seconds)


def _resets_iso(resets_at) -> str:
    """Countdown from an ISO-8601 resetsAt (OpenCode shape)."""
    text = str(resets_at or "").replace("Z", "+00:00").strip()
    try:
        from datetime import datetime, timezone
        reset = datetime.fromisoformat(text)
        if reset.tzinfo is None:
            reset = reset.replace(tzinfo=timezone.utc)
        seconds = int((reset - datetime.now(timezone.utc)).total_seconds())
    except ValueError:
        return ""
    return "now" if seconds <= 0 else _compact_time(seconds)


def _pacing(percent, reset_at, span, now=None) -> str:
    """Usage % vs the share of the window already elapsed (span = window length)."""
    if percent is None or not span or not isinstance(reset_at, (int, float)):
        return ""
    if now is None:
        now = time.time()
    start = reset_at / 1000.0 - span
    if now < start:
        return ""  # reset sits further out than the assumed window: span is wrong
    expected = max(0.0, min(1.0, (now - start) / span)) * 100
    return _pace_verdict(float(percent) - expected)


def _pacing_iso(percent, resets_at, span=None, now=None) -> str:
    """Same verdict from an ISO resetsAt; monthly span = the month before reset."""
    if percent is None:
        return ""
    from datetime import datetime, timezone
    text = str(resets_at or "").replace("Z", "+00:00").strip()
    try:
        reset = datetime.fromisoformat(text)
        if reset.tzinfo is None:
            reset = reset.replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    if now is None:
        now = datetime.now(timezone.utc)
    if span is None:
        span = _one_month_like(reset).total_seconds()
    start = reset.timestamp() - span
    if span <= 0 or now.timestamp() < start:
        return ""
    expected = max(0.0, min(1.0, (now.timestamp() - start) / span)) * 100
    return _pace_verdict(float(percent) - expected)


def _pace_verdict(delta) -> str:
    magnitude = int(abs(delta) + 0.5)  # rounds half away from zero
    if magnitude == 0:
        return "+0%"  # zero never renders as -0%
    return f"{'+' if delta > 0 else '-'}{magnitude}%"


def _one_month_like(reset):
    """Span of the month preceding reset (28-31 days, calendar-correct)."""
    from datetime import timedelta
    y, m = reset.year, reset.month
    if m == 1:
        y, m = y - 1, 12
    else:
        m -= 1
    prev = reset.replace(y, m)  # same day-of-month in the previous month
    return timedelta(days=(reset - prev).days)


# Single source of truth for the footer wrapper: plain text, no emphasis markers.
_FOOTER_MD = "{line}"

# Both row families belong to THIS plugin now: NanoGPT rows carry the provider
# prefix, OpenCode rows are `5h/wk/mo <n>%` or `Go: …`. `%`/`?` after the number
# is required on the bare NanoGPT labels — without it prose ("day 1 of the
# sprint", "img 2048x2048 upscale") matches and gets deleted.
_NANO_ROW_RE = re.compile(r"^(?:NanoGPT: (?:day|wk|img|tok)|(?:day|img|tok)) (?:\d+(?:\.\d+)?%|\?)")
_GO_ROW_RE = re.compile(r"^(?:Go: )?(?:\d+h|wk|mo) \d+(?:\.\d+)?%")


def _is_footer_line(line: str) -> bool:
    s = line.strip().strip(" *_`")
    if s.startswith("NanoGPT:") and (" · " in s or s == "NanoGPT: ..."):
        return True
    if s.startswith("Go:") and (" · " in s or s.endswith("...")):
        return True
    return bool(_NANO_ROW_RE.match(s)) or bool(_GO_ROW_RE.match(s))


def _strip_footers(text: str) -> str:
    kept = []
    for ln in text.split("\n"):
        if _is_footer_line(ln):
            continue
        if ln.strip() == "" and (not kept or kept[-1].strip() == ""):
            continue
        kept.append(ln)
    return "\n".join(kept).rstrip()


_BUDGET = 50  # visible chars per footer line


def _paced(percent) -> bool:
    try:
        return float(percent) >= 10
    except (TypeError, ValueError):
        return False


def _segment_text(segment):
    label, pct, pace, reset = segment
    text = f"{label} {pct}%" if pct != "?" else f"{label} ?"
    if pace and _paced(pct):
        text += f" ({pace})"
    if reset:
        text += f" {reset}"
    return text


def _render_footer(segments, budget=_BUDGET, lead="", row=None):
    """L0 single line -> L1 drop the first reset -> one line per quota.
    `lead` prefixes L0/L1, `row` prefixes each line of the L2 fallback."""
    if not segments:
        return ""
    if row is None:
        row = lead
    full = lead + " · ".join(_segment_text(s) for s in segments)
    if len(full) <= budget:
        return full
    label, pct, pace, _ = segments[0]
    trimmed = [(label, pct, pace, "")] + list(segments[1:])
    one_line = lead + " · ".join(_segment_text(s) for s in trimmed)
    if len(one_line) <= budget:
        return one_line
    return "\n".join(row + _segment_text(s) for s in segments)


def _nano_segments(data):
    out = []
    for key, label, span in _NANO_QUOTAS:
        quota = data.get(key)
        if not isinstance(quota, dict):
            continue  # window not configured for this account
        raw = quota.get("percentUsed")
        if raw is None:
            if not quota.get("degraded"):
                continue
            pct, pace = "?", ""  # lookup failed: unknown, never 0
        else:
            try:
                percent = float(raw) * 100  # fraction -> percent
            except (TypeError, ValueError):
                continue  # one malformed quota must not kill the whole footer
            pct = str(int(round(percent)))
            pace = _pacing(percent, quota.get("resetAt"), span)
        out.append((label, pct, pace, _resets_ms(quota.get("resetAt"))))
    return out


def _opencode_segments(data):
    windows = data.get("usage") or {}
    out = []
    for key, label in _GO_WINDOWS:
        w = windows.get(key)
        if isinstance(w, dict) and w.get("percent") is not None:
            pct = w["percent"]
            pace = _pacing_iso(pct, w.get("resetsAt"), span=_GO_SPANS.get(key))
            out.append((label, str(pct), pace, _resets_iso(w.get("resetsAt"))))
    return out


def _usage_line():
    lines = []
    nano = _fetch_nano()
    if nano:
        line = _render_footer(_nano_segments(nano), lead="NanoGPT: ")
        if line:
            lines.append(line)
    go = _fetch_opencode()
    if go:
        line = _render_footer(_opencode_segments(go), row="Go: ")
        if line:
            lines.append(line)
    return "\n".join(lines)


def transform_llm_output(response_text, model=None, platform=None, session_id=None, **kwargs):
    try:
        if not platform or platform == "cli":
            return None
        if not response_text or not response_text.strip():
            return None
        # Strip only when a footer row is actually present: _strip_footers also
        # collapses blank-line runs (including inside code fences), and the
        # contract is append-only — a footer-less reply must come back unchanged.
        has_footer = any(_is_footer_line(ln) for ln in response_text.split("\n"))
        cleaned = _strip_footers(response_text) if has_footer else response_text
        line = _usage_line()
        if line:
            body = cleaned.rstrip()
            return (body + "\n\n" if body else "") + _FOOTER_MD.format(line=line)
        return cleaned if has_footer else None
    except Exception as exc:
        logger.debug("provider-usage transform failed: %s", exc)
        return None


def _strip_message_content(content):
    if isinstance(content, str):
        if not any(_is_footer_line(ln) for ln in content.split("\n")):
            return None
        cleaned = _strip_footers(content)
        return cleaned if cleaned != content else None
    if isinstance(content, list):
        parts, changed = [], False
        for part in content:
            text = part.get("text") if isinstance(part, dict) else None
            if isinstance(text, str) and any(_is_footer_line(ln) for ln in text.split("\n")):
                cleaned = _strip_footers(text)
                if cleaned != text:
                    part = dict(part)
                    part["text"] = cleaned
                    changed = True
            parts.append(part)
        return parts if changed else None
    return None


def strip_footers_from_request(**kwargs):
    """llm_request middleware: drop footer rows from assistant history."""
    try:
        request = kwargs.get("request")
        if not isinstance(request, dict):
            return None
        new_request, changed = None, False
        for key in ("messages", "input"):
            items = request.get(key)
            if not isinstance(items, list):
                continue
            new_items = None
            for i, item in enumerate(items):
                if not isinstance(item, dict) or item.get("role") != "assistant":
                    continue
                cleaned = _strip_message_content(item.get("content"))
                if cleaned is None:
                    continue
                if new_items is None:
                    new_items = list(items)
                new_items[i] = {**item, "content": cleaned}
                changed = True
            if new_items is not None:
                if new_request is None:
                    new_request = dict(request)
                new_request[key] = new_items
        if not changed:
            return None
        return {"request": new_request, "source": "provider-usage",
                "reason": "strip usage footers from history"}
    except Exception as exc:
        logger.debug("provider-usage request strip failed: %s", exc)
        return None


def register(ctx):
    ctx.register_hook("transform_llm_output", transform_llm_output)
    ctx.register_middleware("llm_request", strip_footers_from_request)
