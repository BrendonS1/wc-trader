from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TargetPosition:
    symbol: str
    side: str  # 'LONG'|'SHORT'
    qty: int
    r60: float
    atr: float


def qty_from_atr_risk(risk_usd: float, atr: float) -> int:
    if atr is None or atr <= 0 or math.isnan(float(atr)):
        return 0
    if risk_usd <= 0:
        return 0
    return int(math.floor(risk_usd / atr))
