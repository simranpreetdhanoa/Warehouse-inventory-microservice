import json
import os

import boto3
import pytest
from moto import mock_aws

REGION = "us-east-1"


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Fake credentials so nothing can ever reach real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("INVENTORY_TABLE", "Inventory")


@pytest.fixture
def aws(monkeypatch):
    """Spin up an in-memory DynamoDB table + SNS topic, with an SQS queue
    subscribed to the topic so tests can read what was published."""
    with mock_aws():
        ddb = boto3.client("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName="Inventory",
            KeySchema=[{"AttributeName": "sku", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "sku", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        sns = boto3.client("sns", region_name=REGION)
        topic_arn = sns.create_topic(Name="reorder-alerts")["TopicArn"]
        monkeypatch.setenv("REORDER_TOPIC_ARN", topic_arn)

        sqs = boto3.client("sqs", region_name=REGION)
        queue_url = sqs.create_queue(QueueName="reorder-test")["QueueUrl"]
        queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)

        def published_messages():
            msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10).get("Messages", [])
            return [json.loads(json.loads(m["Body"])["Message"]) for m in msgs]

        yield {"published": published_messages, "topic_arn": topic_arn}


def api_event(method, resource, sku=None, body=None):
    """Build a minimal API Gateway proxy event."""
    return {
        "httpMethod": method,
        "resource": resource,
        "pathParameters": {"sku": sku} if sku else None,
        "body": json.dumps(body) if body is not None else None,
    }
