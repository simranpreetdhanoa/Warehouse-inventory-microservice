"""DynamoDB access layer. All stock changes are single atomic UpdateItem calls."""
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from inventory import config


class ItemNotFound(Exception):
    pass


class InsufficientStock(Exception):
    pass


class ItemAlreadyExists(Exception):
    pass


def _table():
    return boto3.resource("dynamodb", region_name=config.region()).Table(config.table_name())


def _to_plain(item: dict) -> dict:
    """Convert DynamoDB Decimals into int/float so they can be JSON-serialised."""
    out = {}
    for k, v in item.items():
        if isinstance(v, Decimal):
            out[k] = int(v) if v == v.to_integral_value() else float(v)
        else:
            out[k] = v
    return out


def create_item(item: dict) -> dict:
    record = {k: Decimal(str(v)) if isinstance(v, (int, float)) else v for k, v in item.items()}
    record.setdefault("reorder_pending", False)
    try:
        _table().put_item(Item=record, ConditionExpression="attribute_not_exists(sku)")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ItemAlreadyExists(item["sku"]) from e
        raise
    return _to_plain(record)


def get_item(sku: str) -> dict:
    resp = _table().get_item(Key={"sku": sku})
    if "Item" not in resp:
        raise ItemNotFound(sku)
    return _to_plain(resp["Item"])


def reserve_stock(sku: str, qty: int) -> dict:
    """Atomically decrement stock. The condition runs inside DynamoDB, so two
    concurrent orders can never both take the last unit (no over-allocation)."""
    try:
        resp = _table().update_item(
            Key={"sku": sku},
            UpdateExpression="SET quantity = quantity - :q",
            ConditionExpression="attribute_exists(sku) AND quantity >= :q",
            ExpressionAttributeValues={":q": qty},
            ReturnValues="ALL_NEW",
            ReturnValuesOnConditionCheckFailure="ALL_OLD",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            if "Item" not in e.response:
                raise ItemNotFound(sku) from e
            raise InsufficientStock(sku) from e
        raise
    return _to_plain(resp["Attributes"])


def restock(sku: str, qty: int) -> dict:
    """Atomically increment stock and clear the reorder flag."""
    try:
        resp = _table().update_item(
            Key={"sku": sku},
            UpdateExpression="SET quantity = quantity + :q, reorder_pending = :f",
            ConditionExpression="attribute_exists(sku)",
            ExpressionAttributeValues={":q": qty, ":f": False},
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ItemNotFound(sku) from e
        raise
    return _to_plain(resp["Attributes"])


def claim_reorder(sku: str) -> bool:
    """Flip reorder_pending False -> True. Only the first caller wins, so a burst
    of orders produces exactly one SNS alert instead of one per order."""
    try:
        _table().update_item(
            Key={"sku": sku},
            UpdateExpression="SET reorder_pending = :t",
            ConditionExpression="reorder_pending = :f",
            ExpressionAttributeValues={":t": True, ":f": False},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
