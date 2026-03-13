from ib_insync import IB

def gross_exposure_usd(ib: IB) -> float:
total = 0.0
for p in ib.positions():
mv = getattr(p, "marketValue", None)
if mv is None:
mv = float(p.position) * float(p.avgCost)
total += abs(float(mv))
return total
