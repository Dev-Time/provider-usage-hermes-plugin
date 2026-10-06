# DESIGN — nanogpt-usage

Status: approved by Wyatt 2026-10-05 (clarify: "Go, build it", quotas only,
git init, no push). Research below, implementation notes at the end.

## Goal

Same niche as `opencode-usage`: an automatic usage footer on gateway messages,
for NanoGPT instead of OpenCode Go. Workspace `/workspace/nanogpt-usage-plugin`,
reference implementation `/workspace/opencode-usage-plugin`.

## Endpoints researched 2026-10-05 (docs.nano-gpt.com)

| Endpoint | Auth | Returns |
|---|---|---|
| `GET https://api.nano-gpt.com/api/subscription/v1/usage` (alias `/api/v1/subscription/usage`) | inference key (`Authorization: Bearer` or `x-api-key`) | quotas + `routing` advice for that key |
| `GET https://nano-gpt.com/api/management/v1/subscription/usage` | management token, scope `usage:read` | same quotas, no routing |
| `POST https://api.nano-gpt.com/api/check-balance` | `x-api-key` | `usd_balance`, `nano_balance`, `nanoDepositAddress` |

Chosen: the inference-key endpoint — the key already exists on this box, and it
adds `routing` (whether subscription quota is still available). Balance
segment was explicitly declined (parity with opencode: quotas only).

Payload facts that drive the code:

- `percentUsed` is a **fraction** (0.25 = 25%) and may exceed 1.0 → ×100, rounded.
- `resetAt` is **epoch milliseconds**, not the ISO string opencode returns.
- Quota object `null` = window not configured → omit the segment entirely.
- Counters null with `degraded: true` = lookup failed → render `?`, never 0.
- Quotas count **input tokens** (and images), not requests or dollars.
- Window set is server-driven (`limits`): `dailyInputTokens`,
  `weeklyInputTokens`, `dailyImages`, plus `tokens` for token-based trials.

## Credential resolution

1. `NANOGPT_API_KEY` (declared in `plugin.yaml`, masked install prompt)
2. `HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY` — already present in `/hermes/.env`
   and `/workspace/litellm/.env` (provider `custom:nanogpt`)
3. `resolve_runtime_provider(requested="custom:nanogpt")`, accepted only when
   the resolved provider name contains `nano` — never send another provider's
   key to nano-gpt.com.

## Rendering contract

- Prefix every emitted line with `NanoGPT: `. Mandatory, not cosmetic: the
  opencode-usage matcher eats bare `wk …` / `mo …` / `<n>h …` rows, so a
  bare-leading nanogpt row would be deleted by the *other* plugin and vice
  versa. `_FOOTER_ROW_RE` in this plugin likewise refuses bare `wk`/`mo`/`<n>h`.
- Ladder identical to the reference: L0 single line → L1 drops the first
  segment's reset → one line per quota, `_BUDGET` = 50 visible chars.
- Pace renders only past 10% usage; label/pct/reset order unchanged.
- Footer wrapper is the single plain-text template `_FOOTER_MD = "{line}"`
  (golden test enforces one definition, two render sites, no emphasis markers).
- Gateway-only: `platform == "cli"` (and unset) is left untouched.

## Pacing windows

Spans come from the quota key: `dailyInputTokens`/`dailyImages` → 24h,
`weeklyInputTokens` → 7d, `tokens` (trial) → undocumented → **no pace at all**.
Window start = `resetAt` − span. Guard: when `resetAt` is further out than the
assumed span (span guess wrong, or a longer window), pacing returns `""`
instead of a misleading verdict.

## Repo shape

```
nanogpt-usage/
├── __init__.py        # fetch + render + echo strip + llm_request middleware
├── plugin.yaml        # hooks, provides_middleware, requires_env (secret)
├── README.md          # user-facing: footer, install, config, troubleshooting
├── DESIGN.md          # this doc
├── after-install.md   # post-install hint
├── LICENSE            # MIT
├── .gitignore
└── test_*.py, golden_test.py, live_check.py
```

## Open questions / risks

- **Two footers**: `opencode-usage` and this plugin both register
  `transform_llm_output`. Whether Hermes runs every hook (two footer lines) or
  stops at the first non-None result (only one) is not verified — check after
  install; if only one survives, that is core behavior, not a bug here.
- **Live payload verified 2026-10-05** with the real key:
  `NanoGPT: wk 14% (-3%) 5.9d · img 0% 20.5h` — `active: true`, `state: active`,
  `routing.recommendedMode: subscription`. This account's `dailyInputTokens` is
  `null` (no daily window) and is correctly omitted; `limits` also carries
  `period`, `provider`, `stripeSubscriptionId` and cancellation fields the
  plugin ignores. Response keys beyond the docs' example:
  `allowOverage`, `cancelAt`, `cancelAtPeriodEnd`, `canceledAt`,
  `cancellationReason`, `endedAt`, `graceUntil`, `providerStatus`.
- Daily window semantics (calendar day vs rolling 24h) are not documented;
  pacing assumes `resetAt − 24h`.

## Out of scope

Catalog submission PR, `/usage` slash command, desktop status-bar UI,
multi-account support, LiteLLM-proxy spend tracking (separate tool if wanted).

## Implementation notes (2026-10-05)

- Built offline-first: five test files pass with no network
  (`test_render`, `test_pacing`, `test_middleware`, `test_dedup`, `golden_test`).
- Two design bugs caught by the tests while building: the degraded segment
  rendered `day ?%` (now `day ?`, and the matcher accepts `?`), and pacing
  produced `+50%` for an image quota whose reset was 30d out (now returns no
  verdict when `now < resetAt − span`).
- Cross-plugin safety is asserted in both suites: this plugin never strips
  `Go: … / 5h / wk / mo` rows, and `test_middleware` proves the opencode row
  passes through the llm_request strip untouched.
- `git init` only, no remote (per approval).
