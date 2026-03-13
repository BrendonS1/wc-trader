from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Atr:
    symbol: str
    atr: float


def atr14(symbol: str, highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], lookback: int = 14) -> Atr:
    n = min(len(highs), len(lows), len(closes))
    if n < lookback + 1:
        return Atr(symbol=symbol, atr=0.0)

    trs: list[float] = []
    for i in range(n - lookback, n):
        h = float(highs[i])
        l = float(lows[i])
        prev_close = float(closes[i - 1])
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)

    atr = sum(trs) / len(trs) if trs else 0.0
    return Atr(symbol=symbol, atr=float(atr))
