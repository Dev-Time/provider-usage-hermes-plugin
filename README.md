# provider-usage — Hermes plugin

Shows **NanoGPT and OpenCode Go** subscription usage as a plain-text footer on
every gateway message (Telegram, Discord, Slack, …):

> …reply text…
>
> NanoGPT: day 25% 3.2h · wk 18% (-3%) 3.1d
> 5h 4% 1.1h · wk 8% 5.8d · mo 55% (-16%) 8.7d

- **NanoGPT row**: `day / wk` input-token quotas, `img` image quota — counts are
  read from the API response, so a window the account doesn't have isn't shown.
- **OpenCode row**: `5h / wk / mo` rolling, weekly and monthly windows.
- **3.2h / 3.1d** — countdown to that window's own reset time.
- **(-3%)** — ahead/under quota vs. the share of the window already elapsed,
  shown once a window passes 10% usage.

A provider with no key or no quota simply contributes no line; the other one
still renders.

Only CLI sessions are left untouched (the hook skips `platform == "cli"` and
unset platforms) — `desktop`, `tui`, `cron` and the gateway platforms all carry
the footer.

## Requirements

- Hermes with plugin install support (tested against Hermes 0.21.4)
- A NanoGPT key (https://nano-gpt.com/api), an OpenCode Go key
  (https://opencode.ai/zen), or both — each line is optional.

## Install

```bash
hermes plugins install Dev-Time/provider-usage-hermes-plugin
```

The installer clones the repo, security-scans it, prompts once per missing key
(masked; skipped if already set in `~/.hermes/.env`), then asks
`Enable now? [y/N]` — answer `y` and restart Hermes (or `/restart` in the
gateway).

If Hermes asks a confusing tool-override question during enable, answer
**`n`** — this plugin needs no tool overrides (known upstream prompt bug).

## Configuration

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `NANOGPT_API_KEY` | one of the two | — | NanoGPT key. `HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY` is picked up automatically as a fallback. |
| `OPENCODE_GO_API_KEY` | one of the two | — | OpenCode Go key. `OPENCODE_ZEN_API_KEY` is picked up automatically as a fallback. |
| `USAGE_TTL_SECONDS` | no | `120` | Cache lifetime for each usage payload. |

Each key is only ever sent to its own provider's endpoint. Limits and reset
times come from the responses — no machine-specific paths.

Turn it off with the standard switch:

```bash
hermes plugins disable provider-usage
```

## Replaces `opencode-usage`

Hermes keeps only the FIRST non-empty `transform_llm_output` result
(`agent/turn_finalizer.py`) and plugin load order is alphabetical, so two
footer plugins can never both render. This plugin merges both render paths —
the `5h / wk / mo` row is identical to what `opencode-usage` printed. Disable
the old plugin once this one is installed:

```bash
hermes plugins disable opencode-usage
```

## Notes

- NanoGPT quotas count **input tokens** (and images), not requests or dollars;
  `percentUsed` may exceed 100% and a failed lookup renders `?`, never `0%`.
- The transform is append-only: a reply that carries no footer row is returned
  byte-identical, and footer rows are stripped from outgoing assistant history
  (`llm_request` middleware) so the model never echoes them.
- OpenCode's `GO_USAGE_URL` / NanoGPT's `NANO_USAGE_URL` overrides do not
  exist by design — a key must never be forwarded to an arbitrary host.

## Uninstall

```bash
hermes plugins remove provider-usage
```

## Development

Layout: `__init__.py` (plugin code), `plugin.yaml` (manifest),
`after-install.md`, `DESIGN.md`, tests (all offline except `live_check.py`).

```bash
python3 test_render.py       # both render ladders, matcher, end-to-end payloads
python3 test_pacing.py       # epoch-ms and ISO pacing seeds
python3 test_middleware.py   # llm_request history strip + register() wiring
python3 test_dedup.py        # one footer block, idempotent, append-only
python3 golden_test.py       # byte-identical consecutive renders
python3 live_check.py        # live API check for both providers (loads ~/.hermes/.env)
```

Secrets live in `~/.hermes/.env` only — never in the repo.
