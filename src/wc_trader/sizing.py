import math

def qty_from_notional(last_price: float, notional_cap: float) -> int:
if last_price is None or last_price <= 0:
return 0
return int(math.floor(notional_cap / last_price))
