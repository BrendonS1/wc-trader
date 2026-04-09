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
    qty: int  # capped qty that fits limits
    requested_qty: int  # original desired qty
    current_qty: float
    target_qty: float
    delta_qty: float  # capped delta represented by this order (+/-qty)
    requested_delta_qty: float
    est_price: Optional[float]
    est_notional: Optional[float]  # capped notional
    requested_notional: Optional[float]
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

    Pricing:
    - Tries `ib.reqTickers()` first (may error without subscriptions).
    - Falls back to `fallback_prices` (e.g., last daily close) when provided.

    Risk:
    - Caps order size to `MAX_TRADE_NOTIONAL_USD` instead of skipping.
    - Limits number of orders per run via `MAX_ORDERS_PER_RUN`.
    """

    signed_target: Dict[str, float] = {}
    for t in targets:
        signed_target[t.symbol] = float(t.qty if t.side == "LONG" else -t.qty)

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

    try:
        contracts = [Stock(sym, "SMART", "USD") for sym, *_ in deltas]
        tickers = ib.reqTickers(*contracts)
        for tk in tickers:
            sym = tk.contract.symbol
            px = None
            try:
                mp = tk.marketPrice()
                if mp is not None and float(mp) == float(mp) and float(mp) > 0:
                    px = float(mp)
            except Exception:
                px = None
            if px is None:
                try:
                    if tk.last is not None and float(tk.last) == float(tk.last) and float(tk.last) > 0:
                        px = float(tk.last)
                except Exception:
                    px = None
            if px is not None and px > 0:
                px_by_sym[sym] = px
    except Exception:
        pass

    if fallback_prices:
        for sym, px in fallback_prices.items():
            if sym not in px_by_sym and px is not None and px > 0:
                px_by_sym[sym] = float(px)

    proposed: List[ProposedOrder] = []
    ts = _ts()
    cap = float(limits.max_trade_notional_usd)

    for sym, cur, tgt, delta in deltas:
        px = px_by_sym.get(sym)
        if px is None:
            continue

        action = "BUY" if delta > 0 else "SELL"

        if action == "BUY" and not limits.allow_long:
            continue
        if action == "SELL" and not limits.allow_short:
            if cur <= 0:
                continue

        requested_qty = int(abs(round(delta)))
        if requested_qty <= 0:
            continue

        requested_notional = float(requested_qty) * float(px)
        qty = requested_qty
        if requested_notional > cap:
            max_qty = int(cap // float(px))
            qty = min(qty, max_qty)

        if qty <= 0:
            continue

        est_notional = float(qty) * float(px)
        if est_notional > cap:
            continue

        capped_delta = float(qty if action == "BUY" else -qty)
        proposed.append(
            ProposedOrder(
                ts_utc=ts,
                symbol=sym,
                action=action,
                qty=qty,
                requested_qty=requested_qty,
                current_qty=cur,
                target_qty=tgt,
                delta_qty=capped_delta,
                requested_delta_qty=delta,
                est_price=px,
                est_notional=est_notional,
                requested_notional=requested_notional,
            )
        )

    max_orders = _env_int("MAX_ORDERS_PER_RUN", 10)
    proposed = sorted(proposed, key=lambda o: abs(o.requested_delta_qty), reverse=True)[:max_orders]
    return proposed


def append_orders_csv(orders: Iterable[ProposedOrder], path: str = "state/orders.csv") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists()

    fieldnames = [
        "ts_utc","symbol","action",
        "qty","requested_qty",
        "current_qty","target_qty",
        "delta_qty","requested_delta_qty",
        "est_price","est_notional","requested_notional",
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
                    "requested_qty": o.requested_qty,
                    "current_qty": o.current_qty,
                    "target_qty": o.target_qty,
                    "delta_qty": o.delta_qty,
                    "requested_delta_qty": o.requested_delta_qty,
                    "est_price": o.est_price,
                    "est_notional": o.est_notional,
                    "requested_notional": o.requested_notional,
                }
            )


def maybe_execute_orders(ib, orders: List[ProposedOrder]) -> None:
    if not orders:
        return
    if not _env_bool("EXECUTE_TRADES", False):
        return
    if _env_bool("DISABLE_TRADING", False):
        return

    for o in orders:
        contract = Stock(o.symbol, "SMART", "USD")
        order = MarketOrder(o.action, o.qty)
        ib.placeOrder(contract, order)
