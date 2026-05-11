# 🔮 Jupiter Signal

**AI-assisted multi-API correlation engine for Jupiter's Developer Platform.**

Cross-references **Price API**, **Tokens API**, and **Prediction Markets API** to detect trading signals no single API exposes — then generates **Trigger API** orders with natural-language strategy justifications readable by AI agents.

Built for the ["Not Your Regular Bounty"](https://superteam.fun/earn/listing/not-your-regular-bounty) — Frontier Hackathon track on Superteam Earn.

## What It Does

```
Price API ─────┐
               ├──→ Signal Engine ──→ Trigger API Order
Tokens API ────┤        │
               │        └──→ Natural-language strategy
Prediction ────┘             (AI-agent readable)
```

Jupiter's APIs were designed to be used independently. `jupiter-signal` chains them together:

1. **Price API** → real-time USD pricing + 24h changes
2. **Tokens API** → verification status, organic scores, market data
3. **Prediction Markets API** → find events related to this token, extract sentiment
4. **Correlation engine** → detect anomalies between spot price movement and prediction market pricing
5. **Trigger API (suggested)** → automatically generate limit orders (single, OCO) based on signal strength

## The "Oh" Factor

Cross-referencing APIs produces signals no single source can give you:

- **Anomaly Detection**: Token surges 20% but prediction markets don't move → market is ahead of (or ignoring) news
- **Sentiment Divergence**: Organic score + verification say "legit", prediction markets say "bearish" → investigate
- **AI-Native Output**: Every signal includes human-readable reasoning → feed directly into an LLM agent that decides whether to execute the suggested Trigger order

## Quick Start

```bash
# Install
pip install -e .

# Set your Jupiter API key (get one at developers.jup.ag/portal)
export JUPITER_API_KEY="your-key-here"

# Scan tokens
jupiter-signal scan SOL JUP BONK

# JSON output (for AI agents)
jupiter-signal scan SOL JUP --json

# Check prediction markets for crypto events
jupiter-signal markets crypto
```

## Output Example

```json
{
  "token": {"symbol": "JUP", "name": "Jupiter"},
  "price": {"usd": 0.4056, "change_24h_pct": 52.9},
  "quality": {"organic_score": 92},
  "signal": {
    "type": "bullish",
    "confidence": 0.85,
    "reasoning": "+52.9% 24h price surge; Organic score 92/100 — genuine activity; Verified token; Prediction markets 72% bullish"
  },
  "suggested_order": {
    "type": "single",
    "direction": "buy_below",
    "triggerPriceUsd": 0.385,
    "reasoning": "Buy JUP below $0.385 (5% below current). Prediction market sentiment + organic score suggest accumulation opportunity."
  }
}
```

## Why This Matters

Jupiter just shipped their Developer Platform. This project:

- **Uses 4 separate Jupiter APIs** (Price, Tokens, Prediction, Trigger)
- **Uses their AI Stack** (Skills, llms.txt, CLI docs) during the build process
- **Is itself AI-native** — JSON-first output designed for AI agent consumption
- **Combines APIs in ways they didn't design for** — the correlation engine treats APIs as composable signals

## Architecture

```
jupiter_signal/
├── __init__.py      # Package metadata
├── apis.py          # Jupiter API wrappers + SignalEngine (420 lines)
└── cli.py           # CLI interface with Rich terminal output + JSON export
```

- **Zero blockchain dependencies** — no RPC, no Solana SDK needed. Jupiter APIs are pure REST/JSON.
- **Async-first** — all API calls are concurrent via httpx/AsyncClient
- **Typed** — Pydantic-style dataclasses throughout
- **Agent-friendly** — JSON output mode is the default for programmatic consumers

## Built With Jupiter's AI Stack

During development, we used:

| Tool | Verdict |
|------|--------|
| **Skills** (`npx skills add jup-ag/agent-skills`) | ✅ Excellent for API discovery, mediocre for code generation |
| **llms.txt** | ✅ Great as entry point, filename edge case caused issues |
| **CLI docs** (`developers.jup.ag/docs/ai/cli`) | ✅ Clear docs, pre-v1 instability noted |
| **Docs MCP** | ❌ Not tested in this build (filesystem access sufficed) |

Full DX Report: [`DX-REPORT.md`](DX-REPORT.md)

## License

MIT — Atlas Nexus, 2026
