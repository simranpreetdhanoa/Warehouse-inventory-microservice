"""AWS Lambda entry point behind API Gateway (REST, proxy integration).

Routes:
  POST /items                 create an item
  GET  /items/{sku}           read an item
  POST /items/{sku}/reserve   {"quantity": n}  -> atomic decrement
  POST /items/{sku}/restock   {"quantity": n}  -> atomic increment
"""
import json
import logging

from inventory import repository, service

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REQUIRED_FIELDS = ("sku", "name", "quantity")
NUMERIC_FIELDS = ("quantity", "avg_daily_demand", "demand_std_dev", "lead_time_days", "reorder_qty")


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


class BadRequest(Exception):
    pass


def _parse_body(event: dict) -> dict:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        raise BadRequest("body must be valid JSON") from e
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    return body


def _positive_int(body: dict, field: str = "quantity") -> int:
    value = body.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise BadRequest(f"'{field}' must be a positive integer")
    return value


def _validate_item(body: dict) -> dict:
    missing = [f for f in REQUIRED_FIELDS if f not in body]
    if missing:
        raise BadRequest(f"missing fields: {', '.join(missing)}")
    for f in NUMERIC_FIELDS:
        if f in body and (not isinstance(body[f], (int, float)) or isinstance(body[f], bool) or body[f] < 0):
            raise BadRequest(f"'{f}' must be a non-negative number")
    if not isinstance(body["quantity"], int):
        raise BadRequest("'quantity' must be an integer")
    allowed = set(REQUIRED_FIELDS) | set(NUMERIC_FIELDS)
    return {k: v for k, v in body.items() if k in allowed}


def lambda_handler(event, context):
    method = event.get("httpMethod")
    resource = event.get("resource")
    sku = (event.get("pathParameters") or {}).get("sku")
    logger.info("request %s %s sku=%s", method, resource, sku)

    try:
        if method == "POST" and resource == "/items":
            return _response(201, service.create(_validate_item(_parse_body(event))))
        if method == "GET" and resource == "/items/{sku}":
            return _response(200, service.get(sku))
        if method == "POST" and resource == "/items/{sku}/reserve":
            return _response(200, service.reserve(sku, _positive_int(_parse_body(event))))
        if method == "POST" and resource == "/items/{sku}/restock":
            return _response(200, service.restock(sku, _positive_int(_parse_body(event))))
        return _response(404, {"error": "route not found"})
    except BadRequest as e:
        return _response(400, {"error": str(e)})
    except repository.ItemNotFound:
        return _response(404, {"error": f"item '{sku}' not found"})
    except repository.InsufficientStock:
        return _response(409, {"error": f"insufficient stock for '{sku}'"})
    except repository.ItemAlreadyExists as e:
        return _response(409, {"error": f"item '{e}' already exists"})
    except Exception:
        logger.exception("unhandled error")
        return _response(500, {"error": "internal server error"})
