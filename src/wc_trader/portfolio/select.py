from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from wc_trader.signals.tsmom import TsmomSignal


@dataclass(frozen=True)
class Selection:
    longs: List[TsmomSignal]
    shorts: List[TsmomSignal]
    wc: List[TsmomSignal]


def select_2_2_2(signals: Iterable[TsmomSignal]) -> Selection:
    sigs = list(signals)

    pos = sorted([s for s in sigs if s.r60 > 0], key=lambda s: s.r60, reverse=True)
    neg = sorted([s for s in sigs if s.r60 < 0], key=lambda s: s.r60)  # most negative first

    longs = pos[:2]
    shorts = neg[:2]

    used = {s.symbol for s in longs + shorts}
    remaining = [s for s in sigs if s.symbol not in used and s.sign != 0]
    wc = sorted(remaining, key=lambda s: abs(s.r60), reverse=True)[:2]

    return Selection(longs=longs, shorts=shorts, wc=wc)
