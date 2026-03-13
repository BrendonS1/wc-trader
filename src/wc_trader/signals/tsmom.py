from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class TsmomSignal:
    symbol: str
    r60: float
    sign: int  # -1, 0, +1


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def r60_from_closes(symbol: str, closes: Sequence[float], lookback: int = 60) -> TsmomSignal:
    if len(closes) < lookback + 1:
        return TsmomSignal(symbol=symbol, r60=0.0, sign=0)

    start = float(closes[-(lookback + 1)])
    end = float(closes[-1])
    if start <= 0:
        return TsmomSignal(symbol=symbol, r60=0.0, sign=0)

    r = (end / start) - 1.0
    return TsmomSignal(symbol=symbol, r60=r, sign=_sign(r))
