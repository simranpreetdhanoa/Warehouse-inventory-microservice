import pytest

from inventory.safety_stock import needs_reorder, reorder_point, safety_stock


def test_safety_stock_formula():
    # 1.65 * 4 * sqrt(9) = 19.8 -> 20
    assert safety_stock(demand_std_dev=4, lead_time_days=9) == 20


def test_zero_variability_means_zero_safety_stock():
    assert safety_stock(0, 10) == 0


def test_reorder_point_is_lead_time_demand_plus_safety_stock():
    # 10/day * 9 days = 90, + 20 safety stock
    assert reorder_point(avg_daily_demand=10, demand_std_dev=4, lead_time_days=9) == 110


def test_reorder_point_scales_with_demand():
    assert reorder_point(20, 4, 9) > reorder_point(10, 4, 9)


@pytest.mark.parametrize("args", [(-1, 5), (5, -1)])
def test_negative_inputs_rejected(args):
    with pytest.raises(ValueError):
        safety_stock(*args)


@pytest.mark.parametrize("qty,rop,expected", [(5, 10, True), (10, 10, True), (11, 10, False)])
def test_needs_reorder(qty, rop, expected):
    assert needs_reorder(qty, rop) is expected
