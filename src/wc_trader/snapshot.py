from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_rows(path: str, fieldnames: list[str], rows: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def snapshot_positions(ib, path: str = "state/positions.csv") -> Dict[str, float]:
    """Append one row per IB position; return symbol->qty map for diffing."""
    ts = _ts()
    pos = ib.positions()

    rows = []
    sym_qty: Dict[str, float] = {}

    for p in pos:
        sym = getattr(p.contract, "symbol", None)
        if not sym:
            continue
        qty = float(p.position)
        sym_qty[sym] = sym_qty.get(sym, 0.0) + qty

        rows.append(
            {
                "ts_utc": ts,
                "account": p.account,
                "symbol": sym,
                "secType": getattr(p.contract, "secType", ""),
                "currency": getattr(p.contract, "currency", ""),
                "qty": qty,
                "avg_cost": float(p.avgCost) if p.avgCost is not None else None,
            }
        )

    _write_rows(
        path=path,
        fieldnames=["ts_utc", "account", "symbol", "secType", "currency", "qty", "avg_cost"],
        rows=rows,
    )

    return sym_qty


def snapshot_targets(targets, current_qty: Dict[str, float], path: str = "state/targets.csv") -> None:
    """Append one row per target, including delta vs current holdings."""
    ts = _ts()

    rows = []
    for t in targets:
        cur = float(current_qty.get(t.symbol, 0.0))
        signed_target = float(t.qty if t.side == "LONG" else -t.qty)
        rows.append(
            {
                "ts_utc": ts,
                "symbol": t.symbol,
                "side": t.side,
                "target_qty": int(t.qty),
                "signed_target_qty": signed_target,
                "current_qty": cur,
                "delta_qty": signed_target - cur,
                "r60": float(t.r60),
                "atr": float(t.atr),
            }
        )

    _write_rows(
        path=path,
        fieldnames=[
            "ts_utc",
            "symbol",
            "side",
            "target_qty",
            "signed_target_qty",
            "current_qty",
            "delta_qty",
            "r60",
            "atr",
        ],
        rows=rows,
    )
