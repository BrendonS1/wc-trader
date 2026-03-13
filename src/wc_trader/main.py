import os
import time
from dotenv import load_dotenv
from ib_insync import IB, Stock, util
from wc_trader.exposure import gross_exposure_usd
from wc_trader.risk import load_risk_limits
from wc_trader.sizing import qty_from_notional

def env_int(name: str, default: int) -> int:
v = os.getenv(name)
return default if v is None or v == "" else int(v)

def main():
load_dotenv()
limits = load_risk_limits()
print("[wc-trader] risk limits:", limits)

host = os.getenv("IBKR_HOST", "127.0.0.1")
port = env_int("IBKR_PORT", 4002)
client_id = env_int("IBKR_CLIENT_ID", 7)
symbol = os.getenv("SANITY_SYMBOL", "F")

ib = IB()
print(f"[wc-trader] connecting to IBKR: host={host} port={port} clientId={client_id}")
ib.connect(host, port, clientId=client_id, timeout=10)

print("[wc-trader] connected:", ib.isConnected())
print("[wc-trader] managedAccounts:", ib.managedAccounts())

current_gross = gross_exposure_usd(ib)
print(f"[risk] current gross exposure (USD): {current_gross:.2f} / {limits.max_gross_exposure_usd:.2f}")

contract = Stock(symbol, "SMART", "USD")
ib.qualifyContracts(contract)
ticker = ib.reqMktData(contract, "", False, False)
print(f"[wc-trader] streaming {symbol} ticks for ~15s...")

start = time.time()
while time.time() - start < 15:
ib.sleep(1)
price = ticker.last or ticker.ask or ticker.bid
qty = qty_from_notional(price, limits.max_trade_notional_usd) if price else 0
proposed_notional = (qty * price) if (qty > 0 and price) else 0.0
allowed = (
qty > 0
and (current_gross + abs(proposed_notional) <= limits.max_gross_exposure_usd)
)
print(f"[tick] {symbol} bid={ticker.bid} ask={ticker.ask} last={ticker.last} -> qty={qty} allowed={allowed}")
ib.disconnect()
print("[wc-trader] done")

if __name__ == "__main__":
util.patchAsyncio()
main()
