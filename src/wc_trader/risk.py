import os
from dataclasses import dataclass

@dataclass(frozen=True)
class RiskLimits:
max_trade_notional_usd: float
max_gross_exposure_usd: float
max_open_positions: int
allow_long: bool
allow_short: bool
def _env_bool(name: str, default: bool) -> bool:
v = os.getenv(name)
if v is None or v == "":
return default
return v.strip().lower() in ("1", "true", "yes", "y", "on")

def load_risk_limits() -> RiskLimits:
return RiskLimits(
max_trade_notional_usd=float(os.getenv("MAX_TRADE_NOTIONAL_USD", "200")),
max_gross_exposure_usd=float(os.getenv("MAX_GROSS_EXPOSURE_USD", "200")),
max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "30")),
allow_long=_env_bool("ALLOW_LONG", True),
allow_short=_env_bool("ALLOW_SHORT", True),
)
