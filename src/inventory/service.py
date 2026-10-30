"""Orchestrates repository + safety stock logic + notifications."""
from inventory import notifier, repository
from inventory.safety_stock import needs_reorder, reorder_point


def _rop(item: dict) -> int:
    return reorder_point(
        item.get("avg_daily_demand", 0),
        item.get("demand_std_dev", 0),
        item.get("lead_time_days", 0),
    )


def reserve(sku: str, qty: int) -> dict:
    item = repository.reserve_stock(sku, qty)
    rop = _rop(item)
    alerted = False
    if needs_reorder(item["quantity"], rop) and repository.claim_reorder(sku):
        notifier.publish_reorder(item, rop)
        alerted = True
    return {"item": item, "reorder_point": rop, "reorder_triggered": alerted}


def restock(sku: str, qty: int) -> dict:
    item = repository.restock(sku, qty)
    return {"item": item, "reorder_point": _rop(item)}


def get(sku: str) -> dict:
    item = repository.get_item(sku)
    return {"item": item, "reorder_point": _rop(item)}


def create(item: dict) -> dict:
    created = repository.create_item(item)
    return {"item": created, "reorder_point": _rop(created)}
