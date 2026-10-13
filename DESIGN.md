# DESIGN — provider-usage (merged nanogpt-usage + opencode-usage)

Status: two approvals from Wyatt, both 2026-10-05. First: "Go, build it"
(NanoGPT quota footer, quotas only, git init, no push). Second, after the
independent review: "Merge: one plugin renders both footers", name
`provider-usage`. Research below, merge record at the end.

## Goal

Same niche as `opencode-usage`: an automatic usage footer on gateway messages,
for NanoGPT (now merged with OpenCode Go). Reference implementation: the
earlier `opencode-usage` plugin (same repo layout and test suite).

## Endpoints researched 2026-10-05 (docs.nano-gpt.com)

| Endpoint | Auth | Returns |
|---|---|---|
| `GET https://api.nano-gpt.com/api/subscription/v1/usage` (alias `/api/v1/subscription/usage`) | inference key (`Authorization: Bearer` or `x-api-key`) | quotas + `routing` advice for that key |
| `GET https://nano-gpt.com/api/management/v1/subscription/usage` | management token, scope `usage:read` | same quotas, no routing |
| `POST https://api.nano-gpt.com/api/check-balance` | `x-api-key` | `usd_balance`, `nano_balance`, `nanoDepositAddress` |

Chosen: the inference-key endpoint — the same key already authenticates inference, and it
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
2. `HERMES_CUSTOM_API_NANO_GPT_COM_API_KEY` — the name Hermes gives a
   custom-provider key for a `nano-gpt.com` endpoint, when one is configured
3. `resolve_runtime_provider(requested="custom:nanogpt")`, accepted only when
   the resolved provider name contains `nano` — never send another provider's
   key to nano-gpt.com.

## Rendering contract

- NanoGPT lines carry the `NanoGPT: ` prefix (originally required so the
  opencode-usage matcher could not eat them; now simply how the row reads).
  OpenCode rows read the same way: `Go: ` prefixes every line (L0/L1 and L2).
- Matcher owns BOTH families and is **end-anchored**: `label + pct` is only a
  footer row when the rest of the line is empty, a pace/reset tail
  (`(+12%)`, `3.2h`, `19d`, `now`), or starts ` · `. Prose such as
  `day 50% more than expected` is not a row and is never stripped.
- Ladder identical to the reference: L0 single line → L1 drops the first
  segment's reset → one line per quota, `_BUDGET` = 50 visible chars.
- Pace renders only past 10% usage; label/pct/reset order unchanged.
- Footer wrapper is the single plain-text template `_FOOTER_MD = "{line}"`
  (golden test enforces one definition, one render site, no emphasis markers).
- Gateway-only: `platform == "cli"` (and unset) is left untouched.

## Pacing windows

Spans come from the quota key: `dailyInputTokens`/`dailyImages` → 24h,
`weeklyInputTokens` → 7d, `tokens` (trial) → undocumented → **no pace at all**.
Window start = `resetAt` − span. Guard: when `resetAt` is further out than the
assumed span (span guess wrong, or a longer window), pacing returns `""`
instead of a misleading verdict.

## Why one plugin (the merge)

Core only ever applies ONE `transform_llm_output` result per turn — see
"Open questions" below — so two footer plugins cannot coexist. Decision:
merge both render paths into this plugin, then disable `opencode-usage`.
What changed in the merge:

- Directory renamed `nanogpt-usage-plugin` → `provider-usage-plugin`
  (git history preserved); manifest `name: provider-usage`.
- Two fetchers behind one `_fetch(which, url, key_fn)` with a per-provider
  cache; key ladders stay isolated (`_nano_key` → nano-gpt.com,
  `_opencode_key` → opencode.ai), both falling back to the guarded
  runtime-provider resolver.
- `_render_footer(segments, budget, lead, row)`: both providers prefix every
  line — `NanoGPT: ` and `Go: ` on L0/L1 and on each L2 row.
- Matcher owns BOTH row families (`_NANO_ROW_RE` + `_GO_ROW_RE`), so history
  cleanup no longer depends on which plugin is installed.
- Tests: `test_render`/`test_pacing` cover both ladders and both
  reset/pacing encodings; `test_dedup` expects one block, one row per provider.

## Repo shape

```
provider-usage/
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

- **Two footers — ANSWERED 2026-10-05, only ONE footer can ever render.**
  `agent/turn_finalizer.py:506-517` loops `_invoke_hook_safely("transform_llm_output", …)`
  and breaks on the first non-empty string (`hermes_cli/plugins.py:111`: "return a
  replacement string (first non-None wins)"). Callback order is registration order
  (`plugins_dispatch.py:229`, `for cb in self._hooks.get(hook_name, [])`), and plugin
  load order is dependency-order with alphabetical ties
  (`plugins_manifest.py:219-265`, `keys = sorted(manifests.keys())`) — so
  `nanogpt-usage` registered before `opencode-usage` and would have won (decision:
  merge both render paths — see "Why one plugin"). **After the rename the sort key
  flipped**: `provider-usage` now sorts AFTER `opencode-usage`, so if the old plugin
  is left enabled, `opencode-usage` wins — the `Go: …` row renders and the NanoGPT
  row silently never appears. Fail-safe direction (no content loss), but it makes
  disabling `opencode-usage` a mandatory part of deploying this plugin.
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
- After the merge this plugin owns BOTH row families: `test_middleware` now
  asserts `Go: …` rows ARE stripped from assistant history (before the merge
  the opposite was asserted, while two plugins shared the row shapes).
- `git init` only, no remote (per approval).

## Review fixes (2026-10-05, independent review → verified then applied)

Both blockers were reproduced by execution before the fix, not taken on trust:

1. **Matcher deleted ordinary prose** — `_FOOTER_ROW_RE` required a number but no
   `%`/`?`, so `day 1 of the challenge`, `img 500 files scanned`,
   `img 2048x2048 upscale`, `day 30.` matched and were stripped from the delivered
   reply AND from assistant history. Now `(?:\d+(?:\.\d+)?%|\?)`, plus
   `_is_footer_line`'s `NanoGPT:` branch requires `" · "` or the exact degenerate
   stub `NanoGPT: ...` (it used to fire on any `NanoGPT: …` line ending in `...`).
   Survivors added to `test_render.py`'s negative list.
2. **Transform was not append-only** — `_strip_footers` collapses blank-line runs
   and ran on every reply, so a footer-less reply came back modified (fenced-code
   blank lines included) and returned non-None even with no data. The strip is now
   gated on `any(_is_footer_line(ln) …)`, mirroring the middleware gate the recipe
   warns about, and the no-data comparison is `has_footer` instead of an asymmetric
   `.strip()` diff. Covered by the new append-only block in `test_dedup.py`.
3. **`NANOGPT_USAGE_URL` removed** — it forwarded the bearer key to any configured
   host (forbidden: never forward a provider key to an arbitrary base URL); the
   partner-domain case is speculative, so the endpoint is now a constant.
4. **`_segments` guard** — a single malformed `percentUsed` now skips that quota
   instead of raising out of `_usage_line` and killing the whole footer.
5. Docs fixed to match verified behavior: README's surfaces claim (only `cli`/unset
   are excluded; `desktop`/`tui`/`cron` DO get the footer), its italic example
   (output is plain, `golden_test` forbids markers), the coexistence claim, and
   `after-install.md` now loads `~/.hermes/.env` before `live_check.py` (otherwise
   it prints `key present: False` from outside the gateway process).

## Second review fixes (2026-10-06, merged plugin — reproduced, then fixed)

1. **Matcher still ate prose by prefix** — requiring `%`/`?` was not enough:
   `_ROW_RE` matched `label + pct` at the START of a line with no line-shape
   requirement, so `day 50% more than expected`, `img 3% larger than baseline`,
   `tok 9% of the budget went` and `wk 3% chance of rain tomorrow` were all
   `True` and got stripped from replies and history. The match is now
   end-anchored through `_looks_like_row`: after `label + pct` only an empty
   remainder, a pace/reset tail, or ` · ` counts as a row. All four strings are
   in `test_render.py`'s negative list; every emitted row shape stays positive.
2. **Strip still rewrote blanks around an echoed footer** — the previous fix
   gated the strip on a footer being present, but `_strip_footers` then collapsed
   EVERY adjacent-blank pair in the text: a reply carrying a fenced block plus a
   footer echo lost its fence's blank run. `_strip_footers` now removes the
   footer row plus at most one blank line on each side (the separator the append
   introduced) and touches nothing else. Covered by the new echo-strip block in
   `test_dedup.py`.
3. **Stale DESIGN sections corrected**: the rendering contract no longer claims
   bare shapes are refused (they are owned and end-anchored now), the load-order
   note records that `provider-usage` sorts AFTER `opencode-usage` (so a missed
   disable loses the NanoGPT row, not the Go row), and the old "never strips
   `Go:` rows" claim is reversed to match `test_middleware`.
