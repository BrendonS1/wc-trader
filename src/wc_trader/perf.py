from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
def _to_float(x: str) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def account_summary_map(ib) -> Dict[str, float]:
    out: Dict[str, float] = {}
    rows = ib.accountSummary()
    for row in rows:
        tag = getattr(row, "tag", None)
        val = getattr(row, "value", None)
        if not tag or val is None:
            continue
        f = _to_float(val)
        if f is None:
            continue
        out[tag] = f
    return out


def append_perf_row(ib, path: str = "state/perf.csv") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    m = account_summary_map(ib)
    row = {
        "ts_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "net_liq": m.get("NetLiquidation"),
        "gross_pos_value": m.get("GrossPositionValue"),
        "unrealized_pnl": m.get("UnrealizedPnL"),
        "realized_pnl": m.get("RealizedPnL"),
        "currency": os.getenv("BASE_CURRENCY", "USD"),
    }

    write_header = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)
