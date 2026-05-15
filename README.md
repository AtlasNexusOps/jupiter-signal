# Jupiter Signal

AI-assisted correlation engine for Jupiter's Developer Platform.

`jupiter-signal` combines Jupiter Price, Tokens and Prediction Markets APIs to produce structured token intelligence for AI agents and analyst workflows. It is designed as an Atlas Nexus proof-of-work project: API composition, clean CLI output, JSON-first automation and readable reasoning.

Built for Superteam Earn's **Not Your Regular Bounty** / Frontier Hackathon track.

## Live mini demo

A static project page is available here:

https://atlasnexusops.github.io/jupiter-signal/

## What it does

```text
Price API ─────┐
               ├──→ Correlation Engine ──→ JSON / CLI report
Tokens API ────┤        │
               │        └──→ Agent-readable reasoning
Prediction ────┘
Markets API
```

The engine cross-references independent Jupiter data surfaces:

1. **Price API** — token price and short-term change.
2. **Tokens API** — verification, organic score and market metadata.
3. **Prediction Markets API** — related crypto events and sentiment context.
4. **Correlation engine** — flags divergence between spot momentum, token quality and prediction-market context.
5. **Structured output** — emits compact JSON for downstream agents, dashboards or review workflows.

## Example output

```json
{
  "token": {
    "symbol": "JUP",
    "name": "Jupiter"
  },
  "price": {
    "usd": 0.4056,
    "change_24h_pct": 52.9
  },
  "quality": {
    "organic_score": 92,
    "verified": true
  },
  "prediction_context": {
    "related_markets": 3,
    "sentiment": "bullish"
  },
  "signal": {
    "type": "momentum_divergence",
    "confidence": 0.85,
    "reasoning": "+52.9% 24h price move, organic score 92/100, verified token, related prediction markets leaning bullish. Review manually before acting."
  }
}
```

## CLI usage

```bash
pip install -e .
export JUPITER_API_KEY="your-key"

jupiter-signal scan SOL JUP BONK
jupiter-signal scan SOL JUP --json
jupiter-signal markets crypto
```

## Why it matters

Jupiter's Developer Platform exposes several useful APIs. The value of this project is in combining them rather than treating them as isolated endpoints.

Useful patterns demonstrated:

- multi-API correlation;
- async REST data collection;
- JSON-first output for AI agents;
- analyst-readable reasoning;
- compact CLI workflow;
- bounty-grade documentation and DX notes.

## Repository structure

```text
jupiter_signal/
├── __init__.py      # Package metadata
├── apis.py          # Jupiter API wrappers and correlation engine
└── cli.py           # CLI interface with Rich terminal output + JSON export

docs/
└── index.html       # Static GitHub Pages mini demo
```

## Built with Jupiter's AI stack

During development, the project used Jupiter's agent-facing documentation surfaces, including Skills and `llms.txt`. Notes are captured in [`DX-REPORT.md`](DX-REPORT.md).

## Scope and disclaimer

This project is a technical demonstration and research workflow. It is not financial advice and does not execute transactions. Any market interpretation should be reviewed manually before operational use.

## License

MIT — Atlas Nexus, 2026
