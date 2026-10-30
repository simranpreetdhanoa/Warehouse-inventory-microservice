"""Publishes reorder alerts to SNS."""
import json

import boto3

from inventory import config


def publish_reorder(item: dict, rop: int) -> str:
    message = {
        "event": "REORDER_REQUIRED",
        "sku": item["sku"],
        "name": item.get("name"),
        "quantity_on_hand": item["quantity"],
        "reorder_point": rop,
        "suggested_order_qty": item.get("reorder_qty", rop * 2),
    }
    resp = boto3.client("sns", region_name=config.region()).publish(
        TopicArn=config.topic_arn(),
        Subject=f"Reorder required: {item['sku']}",
        Message=json.dumps(message),
        MessageAttributes={"sku": {"DataType": "String", "StringValue": item["sku"]}},
    )
    return resp["MessageId"]
