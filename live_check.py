import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from __init__ import _api_key, _usage_line

key = _api_key()
print("key present:", bool(key), "(env names, value hidden)")
print("LIVE:", _usage_line() or "(no data)")
