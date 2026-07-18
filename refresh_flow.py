#!/usr/bin/env python3
"""
异常期权流存档器 —— 把 X(Twitter) 上某异常单播报账号的推文解析成结构化 JSON + MD。

抓取用 opencli (https://www.npmjs.com/package/@jackwener/opencli) 读你自己登录的 X 会话，
解析针对 "flow bot" 常见文案格式（见下方正则）。产物是标准 JSON，任何下游工具都能读。

用法:
    python3 refresh_flow.py                     # 默认账号 FL0WG0D，近 7 天
    python3 refresh_flow.py 2026-06-13          # 指定起始日
    python3 refresh_flow.py 2026-06-13 unusual_whales   # 指定起始日 + 账号
    FLOW_ACCOUNT=someacct FLOW_OUT=/tmp/flow python3 refresh_flow.py

产物:
    data/<ACCOUNT>_latest.json   结构化: flows[]: {time,ticker,side,amount_usd,strike?,expiry?,price?,raw}
    data/<ACCOUNT>_latest.md     人类可读: 按标的聚合(call$ vs put$) + 时间倒序明细

解析的文案格式（flow bot 通用）:
    $TICKER - $XXXK Call/Put buyer
    $X million into these $TICKER calls/puts
    Noteworthy flow ...: $TICKER STRIKE Call/Put (EXP) - $XXXK @ price
换成别的账号时，若文案格式不同，改 parse() 里的正则即可。
"""
import json, re, os, sys, subprocess
from datetime import datetime, timezone, timedelta

ET = timezone(timedelta(hours=-4))
OUT_DIR = os.environ.get("FLOW_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(OUT_DIR, exist_ok=True)


def fetch(account, since):
    """用 opencli 拉某账号自 since 起的推文。返回 dict 列表。"""
    out = subprocess.run(
        ["opencli", "twitter", "search", f"from:{account} since:{since}",
         "--filter", "live", "--limit", "80", "-f", "json"],
        capture_output=True, text=True, timeout=120).stdout
    d = json.loads(out)
    return d if isinstance(d, list) else d.get("tweets") or d.get("data") or d.get("results") or []


def _amt(s):
    s = s.replace("$", "").replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*(million|m|k|K)?", s, re.I)
    if not m:
        return 0
    v = float(m.group(1)); u = (m.group(2) or "").lower()
    return int(v * 1e6 if u in ("million", "m") else (v * 1e3 if u == "k" else v))


def parse(items):
    recs = []
    for t in items:
        try:
            et = datetime.strptime(t.get("created_at", ""), "%a %b %d %H:%M:%S +0000 %Y") \
                .replace(tzinfo=timezone.utc).astimezone(ET)
        except Exception:
            continue
        ts = et.strftime("%Y-%m-%d %H:%M ET")
        txt = (t.get("text") or "").strip()
        # "$X million into these $TICKER calls/puts"
        for m in re.finditer(r"\$?([\d.]+)\s*million into these \$([A-Z]{1,6})\s+(calls?|puts?)", txt, re.I):
            recs.append({"time": ts, "ticker": m.group(2), "side": "call" if "call" in m.group(3).lower() else "put",
                         "amount_usd": int(float(m.group(1)) * 1e6), "raw": f"${m.group(1)}M {m.group(3)}"})
        # "$TICKER - $XXXK Call/Put buyer"
        for m in re.finditer(r"\$([A-Z]{1,6})\s*-\s*\$?([\d.]+[KkMm]?)\s+(Call|Put)\s*buyer", txt):
            recs.append({"time": ts, "ticker": m.group(1), "side": m.group(3).lower(),
                         "amount_usd": _amt(m.group(2)), "raw": f"${m.group(2)} {m.group(3)} buyer"})
        # "Noteworthy flow": "$TICKER STRIKE Call/Put (EXP) - $XXXK @ price"
        for m in re.finditer(r"\$([A-Z]{1,6})\s+([\d.]+)\s+(Call|Put)\s*\(([\d/]+)\)\s*-\s*\$?([\d.]+[KkMm]?)\s*@\s*([\d.]+)", txt):
            recs.append({"time": ts, "ticker": m.group(1), "side": m.group(3).lower(), "strike": float(m.group(2)),
                         "expiry": m.group(4), "amount_usd": _amt(m.group(5)), "price": float(m.group(6)),
                         "raw": f"{m.group(2)}{m.group(3)[0]} {m.group(4)} ${m.group(5)}@{m.group(6)}"})
    seen, uniq = set(), []
    for r in recs:
        k = (r["time"], r["ticker"], r["side"], r.get("amount_usd"), r.get("strike"))
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    uniq.sort(key=lambda r: r["time"], reverse=True)
    return uniq


def write(account, flows, since):
    gen = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    out = {"source": f"@{account}", "url": f"https://x.com/{account}", "generated": gen,
           "window": f"since {since}", "count": len(flows), "flows": flows}
    jpath = os.path.join(OUT_DIR, f"{account}_latest.json")
    json.dump(out, open(jpath, "w"), ensure_ascii=False, indent=2)

    from collections import defaultdict
    agg = defaultdict(lambda: {"call": 0, "put": 0, "n": 0})
    for f in flows:
        a = agg[f["ticker"]]; a[f["side"]] += f.get("amount_usd", 0); a["n"] += 1
    L = [f"# @{account} options flow archive · since {since}",
         f"generated {gen} · {len(flows)} records · https://x.com/{account}", "",
         "## By ticker (call$ vs put$)", "",
         "| ticker | bias | Call$ | Put$ | n |", "|---|---|---|---|---|"]
    for t, a in sorted(agg.items(), key=lambda x: -(x[1]["call"] + x[1]["put"])):
        bias = "🟢calls" if a["call"] > a["put"] * 1.2 else ("🔴puts" if a["put"] > a["call"] * 1.2 else "⚪mixed")
        L.append(f"| {t} | {bias} | ${a['call']/1e6:.2f}M | ${a['put']/1e6:.2f}M | {a['n']} |")
    L += ["", "## Detail (ET, newest first)", ""]
    for f in flows:
        extra = f" {f.get('strike','')}{('/'+f['expiry']) if f.get('expiry') else ''}".rstrip()
        L.append(f"- {f['time']} {'🟢' if f['side']=='call' else '🔴'} **{f['ticker']}** {f['side']} ${f.get('amount_usd',0)/1000:.0f}K{extra}")
    open(os.path.join(OUT_DIR, f"{account}_latest.md"), "w").write("\n".join(L))
    return jpath


if __name__ == "__main__":
    since = sys.argv[1] if len(sys.argv) > 1 else (datetime.now(ET) - timedelta(days=7)).strftime("%Y-%m-%d")
    account = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("FLOW_ACCOUNT", "FL0WG0D")
    flows = parse(fetch(account, since))
    jpath = write(account, flows, since)
    print(f"refreshed {len(flows)} records → {jpath} (+ .md) since {since}")
