from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from ib_insync import MarketOrder, Stock

from wc_trader.risk.risk import RiskLimits


@dataclass(frozen=True)
class ProposedOrder:
    ts_utc: str
    symbol: str
    action: str  # BUY or SELL
    qty: int
    current_qty: float
    target_qty: float
    delta_qty: float
    est_price: Optional[float]
    est_notional: Optional[float]


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return int(v)


def propose_orders(
    ib,
    targets,
    current_qty: Dict[str, float],
    limits: RiskLimits,
    fallback_prices: Optional[Dict[str, float]] = None,
) -> List[ProposedOrder]:
    """Turn target positions into proposed market orders (delta-based).

    Uses live-ish prices (reqTickers) for notional gating. If a price cannot be
    obtained for a symbol, we skip proposing an order for safety.
    """

    # Build signed targets map
    signed_target: Dict[str, float] = {}
    for t in targets:
        signed_target[t.symbol] = float(t.qty if t.side == "LONG" else -t.qty)

    # Compute deltas
    deltas: List[Tuple[str, float, float, float]] = []
    for sym, tgt in signed_target.items():
        cur = float(current_qty.get(sym, 0.0))
        delta = tgt - cur
        if abs(delta) < 1e-9:
            continue
        deltas.append((sym, cur, tgt, delta))

    if not deltas:
        return []

    px_by_sym: Dict[str, float] = {}

    # Try to pull live/delayed prices in batch (may fail without market data subscription)
    try:
        contracts = [Stock(sym, "SMART", "USD") for sym, *_ in deltas]
        tickers = ib.reqTickers(*contracts)
        for tk in tickers:
            sym = tk.contract.symbol
            # prefer marketPrice, fallback last
            px = None
            try:
                mp = tk.marketPrice()
                if mp is not None and float(mp) == float(mp):
                    px = float(mp)
            except Exception:
                px = None
            if px is None:
                try:
                    if tk.last is not None and float(tk.last) == float(tk.last):
                        px = float(tk.last)
                except Exception:
                    px = None
            if px is not None and px > 0:
                px_by_sym[sym] = px
    except Exception:
        pass

    # Fallback to last daily close prices if provided
    if fallback_prices:
        for sym, px in fallback_prices.items():
            if sym not in px_by_sym and px is not None and px > 0:
                px_by_sym[sym] = float(px)

    proposed: List[ProposedOrder] = []
    ts = _ts()

    for sym, cur, tgt, delta in deltas:
        px = px_by_sym.get(sym)
        if px is None:
            # Safety: if we can't price it, don't trade it.
            continue

        action = "BUY" if delta > 0 else "SELL"
        qty = int(abs(round(delta)))
        if qty <= 0:
            continue

        est_notional = float(qty) * float(px)

        # Risk gates
        if est_notional > float(limits.max_trade_notional_usd):
            continue

        if action == "BUY" and not limits.allow_long:
            continue
        if action == "SELL" and not limits.allow_short:
            # NOTE: SELL is also used to reduce longs; this gate is conservative.
            # If you want, we can refine to allow SELL that reduces a long.
            if cur <= 0:
                continue

        proposed.append(
            ProposedOrder(
                ts_utc=ts,
                symbol=sym,
                action=action,
                qty=qty,
                current_qty=cur,
                target_qty=tgt,
                delta_qty=delta,
                est_price=px,
                est_notional=est_notional,
            )
        )

    # Limit how many orders we place per run
    max_orders = _env_int("MAX_ORDERS_PER_RUN", 10)
    proposed = sorted(proposed, key=lambda o: abs(o.delta_qty), reverse=True)[:max_orders]

    return proposed


def append_orders_csv(orders: Iterable[ProposedOrder], path: str = "state/orders.csv") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists()

    fieldnames = [
        "ts_utc",
        "symbol",
        "action",
        "qty",
        "current_qty",
        "target_qty",
        "delta_qty",
        "est_price",
        "est_notional",
    ]

    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        for o in orders:
            w.writerow(
                {
                    "ts_utc": o.ts_utc,
                    "symbol": o.symbol,
                    "action": o.action,
                    "qty": o.qty,
                    "current_qty": o.current_qty,
                    "target_qty": o.target_qty,
                    "delta_qty": o.delta_qty,
                    "est_price": o.est_price,
                    "est_notional": o.est_notional,
                }
            )


def maybe_execute_orders(ib, orders: List[ProposedOrder]) -> None:
    """Place orders only when EXECUTE_TRADES=1."""
    if not orders:
        return

    if not _env_bool("EXECUTE_TRADES", False):
        return

    # Extra kill switch
    if _env_bool("DISABLE_TRADING", False):
        return

    for o in orders:
        contract = Stock(o.symbol, "SMART", "USD")
        order = MarketOrder(o.action, o.qty)
        ib.placeOrder(contract, order)
