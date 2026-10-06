# provider-usage installed

1. Restart Hermes (or `/restart` in the gateway) so the plugin loads.
2. Disable the superseded plugin so only one footer path exists:
   `hermes plugins disable opencode-usage`
3. Send a message from a gateway platform — you should see one or two lines
   (NanoGPT and/or `5h … · wk … · mo …`) appended to the reply.
4. No footer? Check both keys and a live payload (works from a plain shell, it
   loads `~/.hermes/.env` itself):
   `python3 ~/.hermes/plugins/provider-usage/live_check.py`

Turn it off anytime: `hermes plugins disable provider-usage`
