# nanogpt-usage installed

1. Restart Hermes (or `/restart` in the gateway) so the plugin loads.
2. Send a message from a gateway platform (Telegram/Discord/…) — you should
   see `NanoGPT: day … · wk …` appended to the reply.
3. No footer? Check your key: `python3 ~/.hermes/plugins/nanogpt-usage/live_check.py`

Turn it off anytime: `hermes plugins disable nanogpt-usage`
