"""
tests/conftest.py
─────────────────
Shared pytest fixtures and configuration.
"""
import os
import sys

import boto3
import pytest
from moto import mock_aws


# ── Ensure Lambda source directories are importable ───────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for fn in ["ivr-handler", "menu-router", "crm-lookup",
           "callback-scheduler", "recording-processor"]:
    path = os.path.join(REPO_ROOT, "lambda", fn)
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(scope="function", autouse=False)
def aws_credentials():
    """Mocked AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"]     = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"]    = "testing"
    os.environ["AWS_SESSION_TOKEN"]     = "testing"
    os.environ["AWS_DEFAULT_REGION"]    = "ap-south-1"


@pytest.fixture(scope="function")
def dynamodb_tables(aws_credentials):
    """Create all DynamoDB tables used across unit tests."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")

        # CallerProfiles
        ddb.create_table(
            TableName="test-CallerProfiles",
            KeySchema=[{"AttributeName": "PhoneNumber", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PhoneNumber", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # MenuConfig
        ddb.create_table(
            TableName="test-MenuConfig",
            KeySchema=[
                {"AttributeName": "MenuId",  "KeyType": "HASH"},
                {"AttributeName": "Version", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "MenuId",  "AttributeType": "S"},
                {"AttributeName": "Version", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # CallLogs
        ddb.create_table(
            TableName="test-CallLogs",
            KeySchema=[
                {"AttributeName": "ContactId", "KeyType": "HASH"},
                {"AttributeName": "Timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "ContactId", "AttributeType": "S"},
                {"AttributeName": "Timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield ddb
