import json
import os
from pathlib import Path

from dotenv import load_dotenv
from ib_insync import IB, util

from wc_trader.data.ib_history import fetch_daily_bars
from wc_trader.portfolio.select import select_2_2_2
from wc_trader.portfolio.size import TargetPosition, qty_from_atr_risk
from wc_trader.risk.atr import atr14
from wc_trader.signals.tsmom import r60_from_closes


def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    return default if v is None or v == "" else int(v)


def env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    return default if v is None or v == "" else float(v)


def load_universe() -> list[str]:
    p = Path("config/universe.json")
    return list(json.loads(p.read_text()))


def main():
    load_dotenv()

    # IBKR connection (paper via ib-gateway socat port)
    host = os.getenv("IBKR_HOST", "ib-gateway")
    port = env_int("IBKR_PORT", 4004)
    client_id = env_int("IBKR_CLIENT_ID", 7)

    # Strategy params
    risk_usd = env_float("RISK_USD_PER_POSITION", 50.0)
    atr_lookback = env_int("ATR_LOOKBACK", 14)
    lookback = env_int("TSMOM_LOOKBACK", 60)

    universe = load_universe()
    print(f"[tsmom] universe size={len(universe)}")

    ib = IB()
    print(f"[wc-trader] connecting to IBKR: host={host} port={port} clientId={client_id}")
    ib.connect(host, port, clientId=client_id, timeout=10)

    # Use delayed market data if realtime isn't subscribed
    ib.reqMarketDataType(3)

    signals = []
    atrs: dict[str, float] = {}

    for sym in universe:
        db = fetch_daily_bars(ib, sym, days=max(lookback + atr_lookback + 10, 180))
        closes = [b.close for b in db.bars]
        highs = [b.high for b in db.bars]
        lows = [b.low for b in db.bars]

        sig = r60_from_closes(sym, closes, lookback=lookback)
        signals.append(sig)

        a = atr14(sym, highs, lows, closes, lookback=atr_lookback)
        atrs[sym] = a.atr

    sel = select_2_2_2(signals)

    targets: list[TargetPosition] = []

    for s in sel.longs:
        qty = qty_from_atr_risk(risk_usd, atrs.get(s.symbol, 0.0))
        targets.append(TargetPosition(symbol=s.symbol, side="LONG", qty=qty, r60=s.r60, atr=atrs.get(s.symbol, 0.0)))

    for s in sel.shorts:
        qty = qty_from_atr_risk(risk_usd, atrs.get(s.symbol, 0.0))
        targets.append(TargetPosition(symbol=s.symbol, side="SHORT", qty=qty, r60=s.r60, atr=atrs.get(s.symbol, 0.0)))

    for s in sel.wc:
        side = "LONG" if s.sign > 0 else "SHORT"
        qty = qty_from_atr_risk(risk_usd, atrs.get(s.symbol, 0.0))
        targets.append(TargetPosition(symbol=s.symbol, side=side, qty=qty, r60=s.r60, atr=atrs.get(s.symbol, 0.0)))

    print(
        f"[tsmom] selection: longs={[s.symbol for s in sel.longs]} "
        f"shorts={[s.symbol for s in sel.shorts]} wc={[s.symbol for s in sel.wc]}"
    )

    for t in targets:
        print(
            f"[target] {t.side:5s} {t.symbol:5s} qty={t.qty:4d} "
            f"r60={t.r60:+.2%} atr={t.atr:.4f} risk_usd={risk_usd}"
        )

    ib.disconnect()


if __name__ == "__main__":
    util.patchAsyncio()
    main()
