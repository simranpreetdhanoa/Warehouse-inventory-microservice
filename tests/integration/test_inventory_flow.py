"""End-to-end tests: Lambda handler -> DynamoDB -> SNS, all running inside moto."""
import json
import boto3

from inventory import handler
from tests.conftest import api_event

# avg 10/day, std dev 4, 9 day lead time  ->  reorder point = 110
WIDGET = {"sku": "WID-001", "name": "Widget", "quantity": 150,
          "avg_daily_demand": 10, "demand_std_dev": 4, "lead_time_days": 9, "reorder_qty": 300}


def call(method, resource, sku=None, body=None):
    resp = handler.lambda_handler(api_event(method, resource, sku, body), None)
    return resp["statusCode"], json.loads(resp["body"])


def create_widget(**overrides):
    status, _ = call("POST", "/items", body={**WIDGET, **overrides})
    assert status == 201


def reserve(qty, sku="WID-001"):
    return call("POST", "/items/{sku}/reserve", sku, {"quantity": qty})


def test_create_and_get(aws):
    create_widget()
    status, data = call("GET", "/items/{sku}", "WID-001")
    assert status == 200
    assert data["item"]["quantity"] == 150
    assert data["reorder_point"] == 110


def test_duplicate_create_is_rejected(aws):
    create_widget()
    status, _ = call("POST", "/items", body=WIDGET)
    assert status == 409


def test_get_missing_item_returns_404(aws):
    assert call("GET", "/items/{sku}", "NOPE")[0] == 404


def test_reserve_decrements_stock(aws):
    create_widget()
    status, data = reserve(20)
    assert status == 200
    assert data["item"]["quantity"] == 130
    assert data["reorder_triggered"] is False
    assert aws["published"]() == []


def test_reserve_more_than_available_is_rejected_and_stock_unchanged(aws):
    create_widget(quantity=5)
    status, _ = reserve(6)
    assert status == 409
    assert call("GET", "/items/{sku}", "WID-001")[1]["item"]["quantity"] == 5


def test_reserve_missing_item_returns_404(aws):
    assert reserve(1, sku="NOPE")[0] == 404


def test_crossing_reorder_point_publishes_sns_alert(aws):
    create_widget()
    status, data = reserve(45)  # 150 -> 105, below ROP 110
    assert status == 200
    assert data["reorder_triggered"] is True

    messages = aws["published"]()
    assert len(messages) == 1
    assert messages[0]["event"] == "REORDER_REQUIRED"
    assert messages[0]["sku"] == "WID-001"
    assert messages[0]["quantity_on_hand"] == 105
    assert messages[0]["suggested_order_qty"] == 300


def test_only_one_alert_until_restocked(aws):
    create_widget()
    reserve(45)  # triggers
    reserve(5)   # still below ROP, but alert already pending
    reserve(5)
    assert len(aws["published"]()) == 1

    status, data = call("POST", "/items/{sku}/restock", "WID-001", {"quantity": 300})
    assert status == 200
    assert data["item"]["quantity"] == 395
    assert data["item"]["reorder_pending"] is False

    reserve(290)  # 395 -> 105, crosses ROP again -> new alert
    assert len(aws["published"]()) == 1  # queue drained above, so this is the new one


def test_burst_of_orders_never_over_allocates(aws):
    """50 orders for 1 unit each against 20 in stock: exactly 20 succeed and
    stock ends at 0, never negative. The guard is the ConditionExpression
    `quantity >= :q`, which real DynamoDB evaluates atomically per item.
    (Requests run sequentially: moto's in-memory backend is not thread-safe,
    so it cannot reproduce DynamoDB's atomicity under real threads.)"""
    create_widget(quantity=20)
    results = [reserve(1)[0] for _ in range(50)]

    assert results.count(200) == 20
    assert results.count(409) == 30
    item = boto3.resource("dynamodb", region_name="us-east-1").Table("Inventory").get_item(Key={"sku": "WID-001"})["Item"]
    assert item["quantity"] == 0


def test_stale_read_cannot_cause_over_allocation(aws):
    """Classic race: two workers both read quantity=1 and both try to take it.
    With a read-modify-write both would succeed; the atomic conditional update
    lets only the first through."""
    create_widget(quantity=1)
    seen_by_a = call("GET", "/items/{sku}", "WID-001")[1]["item"]["quantity"]
    seen_by_b = call("GET", "/items/{sku}", "WID-001")[1]["item"]["quantity"]
    assert seen_by_a == seen_by_b == 1  # both think one unit is available

    assert reserve(1)[0] == 200  # worker A wins
    assert reserve(1)[0] == 409  # worker B is rejected by DynamoDB
    assert call("GET", "/items/{sku}", "WID-001")[1]["item"]["quantity"] == 0
