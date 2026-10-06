import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Outside the gateway the keys are not in the environment yet; load the user's
# .env directly so this one command works from a plain shell.
for path in (os.path.expanduser("~/.hermes/.env"), "/hermes/.env"):
    try:
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                name = name.strip()
                if name and name.replace("_", "").isalnum():
                    os.environ.setdefault(name, value.strip().strip('"').strip("'"))
    except OSError:
        pass

import __init__ as p

print("nano key:", bool(p._nano_key()), "| opencode key:", bool(p._opencode_key()))
print("LIVE:")
line = p._usage_line()
print(line or "  (no data)")
