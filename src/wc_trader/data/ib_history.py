from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ib_insync import IB, Stock, BarData


@dataclass(frozen=True)
class DailyBars:
    symbol: str
    bars: List[BarData]


def fetch_daily_bars(ib: IB, symbol: str, days: int = 180) -> DailyBars:
    """Fetch daily bars for a US stock from IBKR via SMART.

    Notes:
    - Uses TRADES; if market data is delayed, this still typically works.
    - durationStr is approximate; we request enough to cover 60d return + ATR14.
    """
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)

    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=f"{max(days, 90)} D",
        barSizeSetting="1 day",
        whatToShow="TRADES",
        useRTH=True,
        formatDate=1,
        keepUpToDate=False,
    )
    return DailyBars(symbol=symbol, bars=list(bars))
