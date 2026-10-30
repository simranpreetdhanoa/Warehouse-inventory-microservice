"""Runtime configuration, read from environment variables set by the SAM template."""
import os


def table_name() -> str:
    return os.environ.get("INVENTORY_TABLE", "Inventory")


def topic_arn() -> str:
    return os.environ.get("REORDER_TOPIC_ARN", "")


def region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")
