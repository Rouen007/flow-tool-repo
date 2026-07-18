# options-flow-archive

> 把 X(Twitter) 上异常期权单播报账号的推文，解析成**结构化 JSON + Markdown 存档**，供任何下游工具消费。
> Parse an X options-flow bot's tweets into a structured JSON/Markdown archive for downstream tools.

异常单账号（如 @FL0WG0D、unusual-whales 类）在 X 上以固定文案播报大额期权扫单：
`$NBIS - $1.1M Call buyer`、`$2.4 million into these $INTC calls`、`Noteworthy flow: $CRWV 105 Call (10/16) - $7.5M @ 6.79` …

这个小工具把这些非结构化推文变成**标准 JSON**，让你的选股器 / 交易日报 / 看板能直接读"某标的最近有没有大单、买 call 还是 put、多少钱"，做资金面交叉验证。

---

## 产物

跑一次生成两份（默认在 `data/`）：

**`<ACCOUNT>_latest.json`** — 结构化，给程序读：
```json
{
  "source": "@FL0WG0D",
  "generated": "2026-06-16 07:55 ET",
  "window": "since 2026-06-09",
  "count": 60,
  "flows": [
    {"time": "2026-06-12 11:02 ET", "ticker": "NBIS", "side": "call", "amount_usd": 1100000, "raw": "$1.1M calls"},
    {"time": "2026-06-11 09:07 ET", "ticker": "CRWV", "side": "call", "amount_usd": 7500000,
     "strike": 105.0, "expiry": "10/16", "price": 6.79, "raw": "105C 10/16 $7.5M@6.79"}
  ]
}
```

**`<ACCOUNT>_latest.md`** — 人类可读，按标的聚合 call$ vs put$（🟢calls / 🔴puts / ⚪mixed）+ 时间倒序明细。

## 用法

```bash
python3 refresh_flow.py                                # 默认账号 FL0WG0D，近 7 天
python3 refresh_flow.py 2026-06-13                     # 指定起始日
python3 refresh_flow.py 2026-06-13 unusual_whales      # 起始日 + 账号
FLOW_ACCOUNT=someacct FLOW_OUT=/tmp/flow python3 refresh_flow.py
```

零 pip 依赖（纯标准库）。

### 抓取依赖：opencli + 你自己的 X 登录

推文抓取用 [`opencli`](https://www.npmjs.com/package/@jackwener/opencli)（通过浏览器扩展读你已登录的 X 会话，不需要 X API key）：

```bash
npm install -g @jackwener/opencli
opencli doctor   # 确认 [OK] connected
```

> 换数据源：`refresh_flow.py` 的 `fetch()` 是唯一和 opencli 耦合的地方——你完全可以把它换成 X API、Nitter、或任何能拿到推文的方式，只要返回 `[{created_at, text}, ...]`，后面的解析和存档不变。

### 文案格式

`parse()` 匹配 flow bot 常见三种格式（见代码注释）。**换成文案格式不同的账号时，改 `parse()` 的正则即可**，其余不动。

## 下游怎么用

见 [`examples/consumer.py`](examples/consumer.py) —— 读存档、按 ticker 聚合、给你的多/空候选标 **🟢资金背书 / 🔴背离 / — 无**：

```bash
python3 examples/consumer.py                       # 用 examples/sample_output.json
python3 examples/consumer.py data/FL0WG0D_latest.json
```
```
NBIS   long  → 🟢背书 $1.1M call
HOOD   long  → 🔴背离 $0.3M put
CRWV   long  → 🟢背书 $7.5M call
```

做多看 call 大单为背书、put 为背离；做空反之。把它接进选股器命中列表，就能一眼看出"技术信号有没有真金白银站台"。

## 免责声明

仅为**数据整理工具**。异常期权单只反映某一方的下注，**不构成投资建议**，也无法保证大单方向正确（可能是对冲、可能已平仓）。请结合 OI 变化等自行判断。据此交易，盈亏自负。

## License

MIT
