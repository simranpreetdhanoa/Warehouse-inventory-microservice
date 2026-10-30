"""Handler tests that never touch AWS: the service layer is mocked out."""
import json
from unittest.mock import patch

import pytest

from inventory import handler, repository
from tests.conftest import api_event


def body(resp):
    return json.loads(resp["body"])


def test_unknown_route_returns_404():
    resp = handler.lambda_handler(api_event("DELETE", "/items/{sku}", "A1"), None)
    assert resp["statusCode"] == 404


@pytest.mark.parametrize("payload", [{}, {"quantity": 0}, {"quantity": -3}, {"quantity": "5"}, {"quantity": True}])
def test_reserve_rejects_bad_quantity(payload):
    resp = handler.lambda_handler(api_event("POST", "/items/{sku}/reserve", "A1", payload), None)
    assert resp["statusCode"] == 400


def test_invalid_json_returns_400():
    event = api_event("POST", "/items/{sku}/reserve", "A1")
    event["body"] = "{not json"
    assert handler.lambda_handler(event, None)["statusCode"] == 400


def test_create_requires_fields():
    resp = handler.lambda_handler(api_event("POST", "/items", body={"sku": "A1"}), None)
    assert resp["statusCode"] == 400
    assert "name" in body(resp)["error"]


def test_insufficient_stock_maps_to_409():
    with patch("inventory.service.reserve", side_effect=repository.InsufficientStock("A1")):
        resp = handler.lambda_handler(api_event("POST", "/items/{sku}/reserve", "A1", {"quantity": 1}), None)
    assert resp["statusCode"] == 409


def test_unexpected_error_maps_to_500():
    with patch("inventory.service.get", side_effect=RuntimeError("boom")):
        resp = handler.lambda_handler(api_event("GET", "/items/{sku}", "A1"), None)
    assert resp["statusCode"] == 500
    assert "boom" not in resp["body"]  # internal details never leak
