"""
Jupiter API client wrappers.

Thin, typed wrappers around Jupiter's REST APIs.
Each method maps to one API endpoint. All return Pydantic models.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.jup.ag"
API_KEY = os.environ.get("JUPITER_API_KEY", "")


def _headers() -> dict[str, str]:
    """Build common request headers."""
    h: dict[str, str] = {"Accept": "application/json"}
    if API_KEY:
        h["x-api-key"] = API_KEY
    return h


# ---------------------------------------------------------------------------
# Result models (lightweight Pydantic-lite via dataclasses)
# ---------------------------------------------------------------------------


@dataclass
class PriceResult:
    mint: str
    usd_price: float | None
    price_change_24h: float | None = None
    block_id: int | None = None


@dataclass
class TokenInfo:
    mint: str
    name: str
    symbol: str
    decimals: int
    verification: str  # "verified" | "unverified" | "banned"
    organic_score: float | None = None
    is_sus: bool = False
    market_cap: float | None = None
    volume_24h: float | None = None
    holders: int | None = None


@dataclass
class PredictionMarket:
    market_id: str
    title: str
    event_title: str
    category: str
    status: str  # "open" | "closed"
    yes_price: float
    no_price: float
    volume_24h: float | None = None
    close_time: str | None = None


@dataclass
class TriggerOrder:
    order_id: str
    input_mint: str
    output_mint: str
    trigger_price_usd: float
    direction: str  # buy_above | buy_below | sell_above | sell_below
    order_type: str  # single | oco | otoco
    status: str
    amount: float
    created_at: str | None = None


@dataclass
class SignalResult:
    """A cross-API signal detected by the correlation engine."""
    token_mint: str
    token_symbol: str
    token_name: str
    current_price: float
    price_change_24h: float | None
    organic_score: float | None
    verification: str
    prediction_markets: list[PredictionMarket] = field(default_factory=list)
    signal_type: str = "neutral"  # bullish | bearish | anomaly | neutral
    confidence: float = 0.0  # 0.0 - 1.0
    reasoning: str = ""
    suggested_order: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class JupiterAPI:
    """Thin wrapper around Jupiter's REST APIs.

    All calls are async-friendly via httpx. Rate-limit errors (429) are
    surfaced as-is — the caller should back off.
    """

    def __init__(self, base_url: str = BASE_URL, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key or API_KEY
        self._client: httpx.AsyncClient | None = None

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        resp = await self._client.get(
            f"{self.base_url}{path}",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json: Any = None) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        resp = await self._client.post(
            f"{self.base_url}{path}",
            headers=_headers(),
            json=json,
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- Price API ----------------------------------------------------------

    async def get_prices(self, mint_ids: list[str]) -> dict[str, PriceResult]:
        """GET /price/v3?ids=mint1,mint2,... — up to 50 mints."""
        data = await self._get("/price/v3", ids=",".join(mint_ids[:50]))
        results: dict[str, PriceResult] = {}
        for mint, info in data.items():
            results[mint] = PriceResult(
                mint=mint,
                usd_price=info.get("usdPrice"),
                price_change_24h=info.get("priceChange24h"),
                block_id=info.get("blockId"),
            )
        return results

    # -- Tokens API ---------------------------------------------------------

    async def search_tokens(self, query: str, limit: int = 10) -> list[TokenInfo]:
        """GET /tokens/v2/search?query=..."""
        data = await self._get("/tokens/v2/search", query=query, limit=limit)
        return [self._parse_token(t) for t in data.get("data", data) if isinstance(data, list) or data.get("data")]

    async def get_token(self, mint: str) -> TokenInfo | None:
        """GET /tokens/v2/token/{mint}"""
        try:
            data = await self._get(f"/tokens/v2/token/{mint}")
            return self._parse_token(data)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    @staticmethod
    def _parse_token(data: dict[str, Any]) -> TokenInfo:
        return TokenInfo(
            mint=data.get("mint", data.get("address", "")),
            name=data.get("name", ""),
            symbol=data.get("symbol", ""),
            decimals=data.get("decimals", 0),
            verification=data.get("verification", "unverified"),
            organic_score=data.get("organicScore"),
            is_sus=data.get("audit", {}).get("isSus", False) if isinstance(data.get("audit"), dict) else False,
            market_cap=data.get("marketCap"),
            volume_24h=data.get("volume24h"),
            holders=data.get("holders"),
        )

    # -- Prediction Markets API ---------------------------------------------

    async def get_events(self, category: str | None = None, status: str = "open",
                         limit: int = 20) -> list[dict[str, Any]]:
        """GET /prediction/v1/events"""
        params: dict[str, Any] = {"status": status, "limit": limit}
        if category:
            params["category"] = category
        data = await self._get("/prediction/v1/events", **params)
        return data if isinstance(data, list) else data.get("events", [])

    async def get_markets(self, event_id: str) -> list[PredictionMarket]:
        """GET /prediction/v1/events/{event_id}/markets"""
        data = await self._get(f"/prediction/v1/events/{event_id}/markets")
        markets = data if isinstance(data, list) else data.get("markets", [])
        return [self._parse_prediction_market(m) for m in markets]

    @staticmethod
    def _parse_prediction_market(data: dict[str, Any]) -> PredictionMarket:
        return PredictionMarket(
            market_id=data.get("marketId", data.get("id", "")),
            title=data.get("title", ""),
            event_title=data.get("eventTitle", ""),
            category=data.get("category", ""),
            status=data.get("status", "open"),
            yes_price=float(data.get("yesPrice", 0)),
            no_price=float(data.get("noPrice", 0)),
            volume_24h=data.get("volume24h"),
            close_time=data.get("closeTime"),
        )

    # -- Trigger API (read-only operations) ---------------------------------

    async def get_trigger_history(self, wallet: str,
                                  limit: int = 20) -> list[TriggerOrder]:
        """GET /trigger/v2/orders/history?wallet=..."""
        data = await self._get("/trigger/v2/orders/history", wallet=wallet, limit=limit)
        orders = data if isinstance(data, list) else data.get("orders", [])
        return [TriggerOrder(
            order_id=o.get("orderId", o.get("id", "")),
            input_mint=o.get("inputMint", ""),
            output_mint=o.get("outputMint", ""),
            trigger_price_usd=float(o.get("triggerPriceUsd", 0)),
            direction=o.get("direction", ""),
            order_type=o.get("orderType", "single"),
            status=o.get("status", ""),
            amount=float(o.get("amount", 0)),
            created_at=o.get("createdAt"),
        ) for o in orders]


# ---------------------------------------------------------------------------
# Cross-API correlation engine
# ---------------------------------------------------------------------------


class SignalEngine:
    """Detects trading signals by cross-referencing Jupiter APIs.

    The core insight: Jupiter's APIs were designed to be used independently.
    By combining Price + Tokens + Prediction Markets, we surface patterns
    no single API exposes.
    """

    def __init__(self, api: JupiterAPI) -> None:
        self.api = api

    async def scan_token(self, mint: str) -> SignalResult:
        """Full cross-API scan for a single token."""
        # Fetch prices + token info in parallel
        price_data, token_info = await asyncio_gather(
            self.api.get_prices([mint]),
            self.api.get_token(mint),
        )

        price = price_data.get(mint)
        current_price = price.usd_price if price else None
        price_change = price.price_change_24h if price else None

        if not token_info:
            return SignalResult(
                token_mint=mint,
                token_symbol="UNKNOWN",
                token_name="Unknown",
                current_price=current_price or 0,
                price_change_24h=price_change,
                signal_type="neutral",
                confidence=0.0,
                reasoning="Token not found in Jupiter registry.",
            )

        # Fetch prediction markets that might relate to this token
        pred_markets = await self._find_related_markets(token_info)

        # Detect signal
        signal_type, confidence, reasoning = self._classify_signal(
            token_info, current_price, price_change, pred_markets
        )

        # Generate suggested order if signal is strong enough
        suggested = None
        if confidence >= 0.5 and current_price and current_price > 0:
            suggested = self._suggest_order(token_info, current_price, signal_type)

        return SignalResult(
            token_mint=mint,
            token_symbol=token_info.symbol,
            token_name=token_info.name,
            current_price=current_price or 0,
            price_change_24h=price_change,
            organic_score=token_info.organic_score,
            verification=token_info.verification,
            prediction_markets=pred_markets,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=reasoning,
            suggested_order=suggested,
        )

    async def _find_related_markets(self, token: TokenInfo) -> list[PredictionMarket]:
        """Find prediction markets whose events mention this token's name/symbol."""
        # Fetch open crypto-category events
        try:
            events = await self.api.get_events(category="crypto", status="open", limit=20)
        except Exception:
            return []

        name_lower = token.name.lower()
        symbol_lower = token.symbol.lower()
        related: list[PredictionMarket] = []

        for event in events:
            event_title = event.get("title", event.get("eventTitle", "")).lower()
            # Simple keyword match — could be enhanced with NLP
            if name_lower in event_title or symbol_lower in event_title:
                event_id = event.get("eventId", event.get("id", ""))
                if event_id:
                    try:
                        markets = await self.api.get_markets(event_id)
                        related.extend(markets)
                    except Exception:
                        continue

        return related

    def _classify_signal(
        self,
        token: TokenInfo,
        price: float | None,
        price_change: float | None,
        pred_markets: list[PredictionMarket],
    ) -> tuple[str, float, str]:
        """Classify the signal type, confidence, and reasoning."""
        confidence = 0.0
        reasons: list[str] = []
        signal_type = "neutral"

        # 1. Price momentum
        if price_change is not None:
            if price_change > 10:
                confidence += 0.15
                reasons.append(f"+{price_change:.1f}% 24h price surge")
            elif price_change > 5:
                confidence += 0.10
                reasons.append(f"+{price_change:.1f}% 24h price increase")
            elif price_change < -10:
                confidence += 0.15
                reasons.append(f"{price_change:.1f}% 24h price drop — potential oversold")
            elif price_change < -5:
                confidence += 0.08
                reasons.append(f"{price_change:.1f}% 24h price decline")

        # 2. Organic score
        if token.organic_score is not None:
            if token.organic_score > 70:
                confidence += 0.15
                reasons.append(f"Organic score {token.organic_score}/100 — genuine activity")
            elif token.organic_score < 20:
                confidence -= 0.10
                reasons.append(f"Low organic score {token.organic_score}/100 — caution advised")

        # 3. Verification
        if token.verification == "verified":
            confidence += 0.05
            reasons.append("Verified token")
        elif token.verification == "banned":
            confidence = 0.0
            reasons.append("⚠️ BANNED TOKEN — do not trade")
            return ("neutral", 0.0, "; ".join(reasons))

        # 4. Suspicious flag
        if token.is_sus:
            confidence -= 0.20
            reasons.append("Flagged as suspicious by audit")

        # 5. Prediction market correlation
        if pred_markets:
            yes_avg = sum(m.yes_price for m in pred_markets) / len(pred_markets)
            if yes_avg > 0.65:
                confidence += 0.20
                signal_type = "bullish"
                reasons.append(f"Prediction markets {yes_avg:.0%} bullish — strong divergence from spot?")
            elif yes_avg < 0.35:
                confidence += 0.15
                signal_type = "bearish"
                reasons.append(f"Prediction markets {yes_avg:.0%} bearish")

        # 6. Volatility anomaly detection
        if price_change is not None and pred_markets:
            yes_avg = sum(m.yes_price for m in pred_markets) / len(pred_markets)
            # Anomaly: big price move but prediction markets aren't pricing it in
            if abs(price_change) > 15 and 0.45 < yes_avg < 0.55:
                signal_type = "anomaly"
                confidence += 0.25
                reasons.append(
                    "ANOMALY: Major price move not reflected in prediction markets — "
                    "market is either ahead of or ignoring this."
                )

        # Final classification
        confidence = min(confidence, 1.0)
        if signal_type == "neutral":
            if confidence >= 0.25:
                signal_type = "bullish" if (price_change or 0) > 0 else "bearish"

        if not reasons:
            reasons.append("No strong signals detected")

        return signal_type, confidence, "; ".join(reasons)

    def _suggest_order(
        self, token: TokenInfo, current_price: float, signal_type: str
    ) -> dict[str, Any]:
        """Generate a suggested Trigger API order based on the signal."""
        SOL_MINT = "So11111111111111111111111111111111111111112"

        if signal_type == "bullish":
            # Buy below current price — expect dip then rise
            trigger_price = round(current_price * 0.95, 6)
            return {
                "type": "single",
                "inputMint": SOL_MINT,
                "outputMint": token.mint,
                "triggerPriceUsd": trigger_price,
                "direction": "buy_below",
                "reasoning": (
                    f"Buy {token.symbol} below ${trigger_price} (5% below current ${current_price:.4f}). "
                    f"Prediction market sentiment + organic score suggest accumulation opportunity."
                ),
            }
        elif signal_type == "bearish":
            trigger_price = round(current_price * 0.90, 6)
            return {
                "type": "single",
                "inputMint": token.mint,
                "outputMint": SOL_MINT,
                "triggerPriceUsd": trigger_price,
                "direction": "sell_below",
                "reasoning": (
                    f"Sell {token.symbol} if it drops below ${trigger_price} (10% below current ${current_price:.4f}). "
                    f"Bearish prediction market sentiment indicates possible further decline."
                ),
            }
        elif signal_type == "anomaly":
            # OCO order: take profit high, stop loss low
            tp = round(current_price * 1.15, 6)
            sl = round(current_price * 0.85, 6)
            return {
                "type": "oco",
                "inputMint": token.mint,
                "outputMint": SOL_MINT,
                "takeProfitPrice": tp,
                "stopLossPrice": sl,
                "direction": "sell_above",
                "ocoDirection": "sell_below",
                "reasoning": (
                    f"Anomaly detected: {token.symbol} shows unusual divergence between spot and prediction markets. "
                    f"OCO order: TP ${tp} (+15%), SL ${sl} (-15%). This captures the volatility while managing risk."
                ),
            }
        else:
            return None


# -- Utility ---------------------------------------------------------------


async def asyncio_gather(*coros):
    """Wrapper that works with or without asyncio event loop setup."""
    import asyncio
    return await asyncio.gather(*coros)
