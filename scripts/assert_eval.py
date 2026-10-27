"""Eval a python expression against the JSON in /tmp/resp_opt.json.

`d` is the parsed response. `['` at expression positions (not preceded by an
identifier char or `]`) is auto-prefixed with `d` so test assertions read like:
  "['results'][0]['symbol']"  ->  d['results'][0]['symbol']
  "len(['rows'])>20"          ->  len(d['rows'])>20
  "0<['pop']<1"               ->  0<d['pop']<1
"""
import json
import re
import sys

expr = sys.argv[1]
try:
    with open("/tmp/resp_opt.json") as f:
        d = json.load(f)
    expr = re.sub(r"(?<![\w\]])\['", "d['", expr)
    print(eval(expr, {"d": d, "len": len, "sum": sum, "any": any, "all": all}))
except Exception as e:
    print("ASSERT_ERR", e)
