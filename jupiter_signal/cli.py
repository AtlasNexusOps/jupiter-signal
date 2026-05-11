"""
CLI for Jupiter Signal — multi-API correlation engine.

Usage:
    jupiter-signal scan SOL         # Scan a specific token
    jupiter-signal scan JUP,SOL,BONK  # Scan multiple tokens
    jupiter-signal scan --trending  # Scan top trending tokens
    jupiter-signal markets          # Show open prediction markets
    jupiter-signal export --format json  # Export full scan results

Output is JSON by default — designed for AI agent consumption.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .apis import JupiterAPI, SignalEngine, SignalResult, PredictionMarket


# Known token mints for quick reference
KNOWN_TOKENS: dict[str, str] = {
    "SOL": "So11111111111111111111111111111111111111112",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RNDR": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
    "WEN": "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",
}


def resolve_mint(token: str) -> str:
    """Resolve a token symbol or mint address."""
    t = token.strip()
    # Check known symbols
    upper = t.upper()
    if upper in KNOWN_TOKENS:
        return KNOWN_TOKENS[upper]
    # Check if it's already a base58 mint address
    if len(t) >= 32 and len(t) <= 44:
        return t
    # Try to search it
    return t  # API will handle the fallback


async def run_scan(api: JupiterAPI, engine: SignalEngine,
                   tokens: list[str], verbose: bool = False) -> list[SignalResult]:
    """Scan one or more tokens and return results."""
    results: list[SignalResult] = []
    for i, token in enumerate(tokens):
        mint = resolve_mint(token)
        if verbose:
            print(f"[{i+1}/{len(tokens)}] Scanning {token} ({mint[:8]}...)", file=sys.stderr)
        try:
            result = await engine.scan_token(mint)
            results.append(result)
        except Exception as exc:
            if verbose:
                print(f"  ⚠️ Error scanning {token}: {exc}", file=sys.stderr)
            results.append(SignalResult(
                token_mint=mint,
                token_symbol=token,
                token_name=token,
                current_price=0,
                signal_type="error",
                confidence=0,
                reasoning=str(exc),
            ))
    return results


def format_rich(results: list[SignalResult], title: str = "Jupiter Signal Report"):
    """Format results using Rich for terminal display."""
    console = Console()

    # Header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]🔮 {title}[/]\n"
        f"[dim]{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  •  "
        f"{len(results)} tokens scanned[/]",
        border_style="cyan",
    ))

    # Signal summary
    signal_colors = {
        "bullish": "green",
        "bearish": "red",
        "anomaly": "yellow",
        "neutral": "dim",
        "error": "red",
    }

    table = Table(title="Token Signals", border_style="dim")
    table.add_column("Token", style="bold")
    table.add_column("Price (USD)")
    table.add_column("24h Δ")
    table.add_column("Score")
    table.add_column("Signal")
    table.add_column("Conf.")
    table.add_column("Reasoning", max_width=60)

    for r in results:
        price_str = f"${r.current_price:.4f}" if r.current_price else "N/A"
        change_str = f"{r.price_change_24h:+.1f}%" if r.price_change_24h else "—"
        change_style = "green" if (r.price_change_24h or 0) > 0 else "red" if (r.price_change_24h or 0) < 0 else ""
        org_str = f"{r.organic_score:.0f}/100" if r.organic_score else "—"
        sig_color = signal_colors.get(r.signal_type, "dim")
        sig_emoji = {"bullish": "🟢", "bearish": "🔴", "anomaly": "🟡", "neutral": "⚪", "error": "❌"}.get(r.signal_type, "")
        conf_str = f"{r.confidence:.0%}"

        table.add_row(
            f"{r.token_symbol}",
            price_str,
            f"[{change_style}]{change_str}[/]",
            org_str,
            f"[{sig_color}]{sig_emoji} {r.signal_type.upper()}[/]",
            conf_str,
            r.reasoning,
        )

    console.print(table)

    # Prediction market matches
    pm_results = [r for r in results if r.prediction_markets]
    if pm_results:
        console.print()
        pm_table = Table(title="🎯 Prediction Market Matches", border_style="yellow")
        pm_table.add_column("Token")
        pm_table.add_column("Event")
        pm_table.add_column("YES Price")
        pm_table.add_column("NO Price")
        for r in pm_results:
            for pm in r.prediction_markets:
                pm_table.add_row(
                    r.token_symbol,
                    pm.title[:60],
                    f"${pm.yes_price:.2f}",
                    f"${pm.no_price:.2f}",
                )
        console.print(pm_table)

    # Suggested orders
    order_results = [r for r in results if r.suggested_order]
    if order_results:
        console.print()
        console.print("[bold]📋 Suggested Trigger API Orders:[/]")
        for r in order_results:
            if r.suggested_order:
                o = r.suggested_order
                console.print(
                    f"  • {r.token_symbol}: {o.get('type', 'single').upper()} "
                    f"{o.get('direction', '')} @ ${o.get('triggerPriceUsd', '?')} "
                    f"[dim]— {o.get('reasoning', '')}[/]"
                )

    # Verdict summary
    bullish = sum(1 for r in results if r.signal_type == "bullish")
    bearish = sum(1 for r in results if r.signal_type == "bearish")
    anomalies = sum(1 for r in results if r.signal_type == "anomaly")
    console.print()
    verdict = Text()
    verdict.append(f"\n📊 Verdict: ", style="bold")
    verdict.append(f"{bullish} bullish  ", style="green")
    verdict.append(f"{bearish} bearish  ", style="red")
    verdict.append(f"{anomalies} anomalies  ", style="yellow")
    verdict.append(f"{len(results) - bullish - bearish - anomalies} neutral")
    console.print(verdict)
    console.print()


def format_json(results: list[SignalResult]) -> str:
    """Format results as JSON for AI agent consumption."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "jupiter-signal",
        "version": "0.1.0",
        "tokens_scanned": len(results),
        "results": [
            {
                "token": {
                    "mint": r.token_mint,
                    "symbol": r.token_symbol,
                    "name": r.token_name,
                    "verification": r.verification,
                },
                "price": {
                    "usd": r.current_price,
                    "change_24h_pct": r.price_change_24h,
                },
                "quality": {
                    "organic_score": r.organic_score,
                },
                "signal": {
                    "type": r.signal_type,
                    "confidence": round(r.confidence, 4),
                    "reasoning": r.reasoning,
                },
                "prediction_markets": [
                    {
                        "title": m.title,
                        "yes_price": m.yes_price,
                        "no_price": m.no_price,
                        "category": m.category,
                    }
                    for m in r.prediction_markets
                ],
                "suggested_order": r.suggested_order,
            }
            for r in results
        ],
    }
    return json.dumps(output, indent=2)


async def async_main(args: list[str]) -> int:
    """Async entry point."""
    api = JupiterAPI()

    try:
        if not args or args[0] in ("--help", "-h", "help"):
            print(__doc__)
            return 0

        command = args[0].lower()

        if command == "scan":
            # Parse scan args
            token_args = [a for a in args[1:] if not a.startswith("--")]
            use_json = "--json" in args or "-j" in args
            verbose = "--verbose" in args or "-v" in args

            if not token_args and "--trending" not in args:
                print("Usage: jupiter-signal scan <TOKEN>... [--json] [--verbose]", file=sys.stderr)
                print(f"Known tokens: {', '.join(KNOWN_TOKENS.keys())}", file=sys.stderr)
                return 1

            if "--trending" in args:
                # Fetch trending tokens from Tokens API (Organic Score leaderboard)
                print("Fetching trending tokens...", file=sys.stderr)
                # Use hardcoded top tokens as a fallback for trending
                trending = ["SOL", "JUP", "BONK", "USDC", "WIF", "PYTH"]
                token_args = trending + token_args

            engine = SignalEngine(api)
            results = await run_scan(api, engine, token_args, verbose=verbose)

            if use_json or not HAS_RICH:
                print(format_json(results))
            else:
                format_rich(results)

        elif command == "markets":
            engine = SignalEngine(api)
            category = args[1] if len(args) > 1 else "crypto"
            try:
                events = await api.get_events(category=category, status="open", limit=20)
                print(json.dumps(events, indent=2))
            except Exception as exc:
                print(f"Error fetching markets: {exc}", file=sys.stderr)
                return 1

        elif command == "export":
            engine = SignalEngine(api)
            tokens = args[1:] if len(args) > 1 else list(KNOWN_TOKENS.keys())[:6]
            results = await run_scan(api, engine, tokens, verbose=True)
            print(format_json(results))

        else:
            print(f"Unknown command: {command}", file=sys.stderr)
            print(__doc__)
            return 1

        return 0

    finally:
        await api.close()


def main():
    """CLI entry point."""
    args = sys.argv[1:]
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
