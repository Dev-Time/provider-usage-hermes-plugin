"""NanoGPT usage plugin — appends subscription quota percentages to the final
gateway message footer via transform_llm_output."""

import json
import logging
import os
import re
import time
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_USAGE_URL = "https://api.nano-gpt.com/api/subscription/v1/usage"
_state = {"data": None, "fetched_at": 0.0}

# quota key -> (label, window seconds); span drives pacing only, resetAt drives
# the countdown. `tokens` (token trial) has no documented window: no pacing.
_QUOTAS = (
    ("dailyInputTokens", "day", 86400),
    ("weeklyInputTokens", "wk", 7 * 86400),
    ("dailyImages", "img", 86400),
    ("tokens", "tok", None),
)
_PREFIX = "NanoGPT: "


def _ttl():
    try:
        return max(1.0, float(os.environ.get("NANOGPT_USAGE_TTL_SECONDS")))
    except (TypeError, ValueError):
        return 120.0


def _api_key():
    for name in ("NANOGPT_API_KEY", "HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY"):
        key = os.environ.get(name, "")
        if key:
            return key
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime = resolve_runtime_provider(requested="custom:nanogpt")
        # Never send another provider's key to nano-gpt.com (custom providers
        # resolve down the ladder to OpenRouter when the requested one is absent).
        if "nano" in str(runtime.get("provider") or "").lower():
            return str(runtime.get("api_key") or "").strip()
    except Exception:
        pass
    return ""


def _fetch_usage():
    if _state["data"] and time.monotonic() - _state["fetched_at"] < _ttl():
        return _state["data"]
    key = _api_key()
    if not key:
        return None
    try:
        req = Request(DEFAULT_USAGE_URL, headers={"Authorization": f"Bearer {key}",
                                                  "User-Agent": "hermes-agent/0.21 (nanogpt-usage-plugin)"})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        _state["data"] = data
        _state["fetched_at"] = time.monotonic()
        return data
    except Exception as exc:
        logger.debug("nanogpt-usage fetch failed: %s", exc)
        return None


def _compact_time(seconds) -> str:
    if seconds >= 86400:
        days = round(seconds / 86400, 1)
        return f"{int(days)}d" if days == int(days) else f"{days}d"
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds // 60}m"


def _resets_in(reset_at) -> str:
    """Countdown from resetAt (UNIX epoch milliseconds — not ISO like opencode)."""
    if not isinstance(reset_at, (int, float)) or reset_at <= 0:
        return ""
    seconds = int(reset_at / 1000 - time.time())
    if seconds <= 0:
        return "now"
    return _compact_time(seconds)


def _pacing(percent, reset_at, span, now=None) -> str:
    """Usage % vs the share of the window already elapsed (span = window length)."""
    if percent is None or not span or not isinstance(reset_at, (int, float)):
        return ""
    if now is None:
        now = time.time()
    end = reset_at / 1000.0
    start = end - span
    if span <= 0:
        return ""
    if now < start:
        return ""  # reset sits further out than the assumed window: span is wrong
    expected = max(0.0, min(1.0, (now - start) / span)) * 100
    delta = float(percent) - expected
    magnitude = int(abs(delta) + 0.5)  # rounds half away from zero
    if magnitude == 0:
        return "+0%"  # zero never renders as -0%
    return f"{'+' if delta > 0 else '-'}{magnitude}%"


# Single source of truth for the footer wrapper: plain text, no emphasis markers.
_FOOTER_MD = "{line}"

# "NanoGPT: <label> <pct>…" — the bare `wk`/`\d+h`/`mo` shapes belong to the
# opencode-usage plugin and must never be swallowed by this one. `%` or `?` is
# REQUIRED after the number: without it the bare labels match prose lines
# ("day 1 of the sprint", "img 2048x2048 upscale") and delete them.
_FOOTER_ROW_RE = re.compile(r"^(?:NanoGPT: (?:day|wk|img|tok)|(?:day|img|tok)) (?:\d+(?:\.\d+)?%|\?)")


def _is_footer_line(line: str) -> bool:
    s = line.strip().strip(" *_`")
    if s.startswith("NanoGPT:") and (" · " in s or s == "NanoGPT: ..."):
        return True
    return bool(_FOOTER_ROW_RE.match(s))


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


def _render_footer(segments, budget=_BUDGET):
    """L0 single line -> L1 drop the first reset -> one line per quota."""
    if not segments:
        return ""
    full = _PREFIX + " · ".join(_segment_text(s) for s in segments)
    if len(full) <= budget:
        return full
    label, pct, pace, _ = segments[0]
    trimmed = [(label, pct, pace, "")] + list(segments[1:])
    one_line = _PREFIX + " · ".join(_segment_text(s) for s in trimmed)
    if len(one_line) <= budget:
        return one_line
    return "\n".join(_PREFIX + _segment_text(s) for s in segments)


def _segments(data):
    out = []
    for key, label, span in _QUOTAS:
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
        out.append((label, pct, pace, _resets_in(quota.get("resetAt"))))
    return out


def _usage_line():
    data = _fetch_usage()
    if not data:
        return ""
    return _render_footer(_segments(data))


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
        logger.debug("nanogpt-usage transform failed: %s", exc)
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
    """llm_request middleware: drop this plugin's footer rows from assistant history."""
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
        return {"request": new_request, "source": "nanogpt-usage",
                "reason": "strip usage footers from history"}
    except Exception as exc:
        logger.debug("nanogpt-usage request strip failed: %s", exc)
        return None


def register(ctx):
    ctx.register_hook("transform_llm_output", transform_llm_output)
    ctx.register_middleware("llm_request", strip_footers_from_request)
