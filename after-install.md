# nanogpt-usage installed

1. Restart Hermes (or `/restart` in the gateway) so the plugin loads.
2. Send a message from a gateway platform (Telegram/Discord/…) — you should
   see `NanoGPT: day … · wk …` appended to the reply.
3. No footer? Check the key and a live payload (works from a plain shell, it
   loads `~/.hermes/.env` itself):
   `python3 ~/.hermes/plugins/nanogpt-usage/live_check.py`

Note: if `opencode-usage` is also installed, only one footer can appear per
message (Hermes keeps the first). See README → "Coexistence".

Turn it off anytime: `hermes plugins disable nanogpt-usage`
