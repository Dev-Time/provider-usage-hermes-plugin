# nanogpt-usage — Hermes plugin

Shows your NanoGPT subscription quota as a plain-text footer on every gateway
message (Telegram, Discord, Slack, …):

> …reply text…
>
> _NanoGPT: day 25% 3.2h · wk 18% (-3%) 3.1d_

- **day / wk** — input-token quota for the daily and weekly windows
- **img** — the daily image quota, when the account has one
- **tok** — token-trial allowance, when the account is on a trial
- **3.2h / 3.1d** — countdown to that window's own `resetAt`
- **(pace …)** — ahead/under quota vs. the share of the window already
  elapsed, shown once a window passes 10% usage

CLI/desktop sessions are intentionally left untouched; the footer is a
gateway-message feature. Windows are read from the API response — nothing is
hardcoded, and a window the account doesn't have simply isn't shown.

## Requirements

- Hermes with plugin install support (tested against Hermes 0.21.4)
- A NanoGPT API key: https://nano-gpt.com/api

## Install

```bash
hermes plugins install Dev-Time/nanogpt-usage-hermes-plugin
```

The installer clones the repo, security-scans it, prompts once for
`NANOGPT_API_KEY` (masked; skipped if already set in `~/.hermes/.env`), then
asks `Enable now? [y/N]` — answer `y` and restart Hermes (or `/restart` in
the gateway).

If Hermes asks a confusing tool-override question during enable, answer
**`n`** — this plugin needs no tool overrides (known upstream prompt bug).

## Configuration

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `NANOGPT_API_KEY` | yes | — | NanoGPT inference key. `HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY` (the nano-gpt provider key) is picked up automatically as a fallback. |
| `NANOGPT_USAGE_URL` | no | `https://api.nano-gpt.com/api/subscription/v1/usage` | Full usage endpoint override (partner domains use a different host). |
| `NANOGPT_USAGE_TTL_SECONDS` | no | `120` | Cache lifetime for the usage payload. |

Plan tier, limits and reset times come from the response itself — no other
keys, no machine-specific paths.

Turn it off with the standard switch:

```bash
hermes plugins disable nanogpt-usage
```

## Notes

- Quotas count **input tokens** (and images), not requests or dollars.
- `percentUsed` may exceed 100%; a failed lookup renders `?`, never `0%`.
- This plugin and `opencode-usage` can both be installed: each one strips and
  appends only its own footer rows (`NanoGPT: …` vs `Go: … / 5h / wk / mo`).

## Uninstall

```bash
hermes plugins remove nanogpt-usage
```

## Development

Layout: `__init__.py` (plugin code), `plugin.yaml` (manifest),
`after-install.md` (shown by the installer), `DESIGN.md` (design record),
tests (all offline except `live_check.py`).

```bash
python3 test_render.py       # footer render ladder, matcher, end-to-end payload
python3 test_pacing.py       # day/week pacing seeds
python3 test_middleware.py   # llm_request history strip + register() wiring
python3 test_dedup.py        # exactly one footer block, idempotent
python3 golden_test.py       # byte-identical consecutive renders
python3 live_check.py        # live API check (needs the key in env)
```

Secrets: keys live in `~/.hermes/.env` only — never in the repo.
