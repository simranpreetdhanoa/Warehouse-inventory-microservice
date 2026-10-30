"""Pure business logic for dynamic safety stock and reorder points (no AWS calls)."""
import math

# z-score for the desired service level (95% ~ 1.65)
DEFAULT_Z = 1.65


def safety_stock(demand_std_dev: float, lead_time_days: float, z: float = DEFAULT_Z) -> int:
    """Safety stock = z * sigma_daily_demand * sqrt(lead_time)."""
    if demand_std_dev < 0 or lead_time_days < 0:
        raise ValueError("demand_std_dev and lead_time_days must be non-negative")
    return math.ceil(z * demand_std_dev * math.sqrt(lead_time_days))


def reorder_point(avg_daily_demand: float, demand_std_dev: float, lead_time_days: float,
                  z: float = DEFAULT_Z) -> int:
    """Reorder point = expected demand during lead time + safety stock."""
    if avg_daily_demand < 0:
        raise ValueError("avg_daily_demand must be non-negative")
    lead_time_demand = math.ceil(avg_daily_demand * lead_time_days)
    return lead_time_demand + safety_stock(demand_std_dev, lead_time_days, z)


def needs_reorder(quantity: int, rop: int) -> bool:
    return quantity <= rop
