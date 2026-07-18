#!/usr/bin/env python3
"""示例：下游工具如何消费 flow 存档，给一批标的标注资金背书/背离。"""
import json, sys, os
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "sample_output.json")
d = json.load(open(path))

agg = defaultdict(lambda: {"call": 0, "put": 0})
for f in d["flows"]:
    agg[f["ticker"]][f["side"]] += f.get("amount_usd", 0)

def flow_tag(ticker, side):
    """side='long'/'short'。返回资金背书/背离/无。"""
    a = agg.get(ticker.upper())
    if not a or (a["call"] == 0 and a["put"] == 0):
        return "— no flow"
    dom = "call" if a["call"] >= a["put"] else "put"
    amt = a[dom] / 1e6
    confirm = (side == "long" and dom == "call") or (side == "short" and dom == "put")
    return f"{'🟢背书' if confirm else '🔴背离'} ${amt:.1f}M {dom}"

# demo：假设你的多头候选
for tk, side in [("NBIS", "long"), ("HOOD", "long"), ("CRWV", "long")]:
    print(f"{tk:6} {side:5} → {flow_tag(tk, side)}")
