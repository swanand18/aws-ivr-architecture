"""
tests/integration/test_smoke.py
─────────────────────────────────
Smoke tests that run against the deployed stack.
Require AWS credentials with read permissions.
Run: pytest integration/test_smoke.py --env=prod --region=ap-south-1
"""
import json
import os
import time

import boto3
import pytest


def pytest_addoption(parser):
    parser.addoption("--env",    action="store", default="prod")
    parser.addoption("--region", action="store", default="ap-south-1")


@pytest.fixture(scope="session")
def config(request):
    env    = request.config.getoption("--env")
    region = request.config.getoption("--region")
    return {"env": env, "region": region, "prefix": f"ivr-{env}"}


@pytest.fixture(scope="session")
def aws_clients(config):
    region = config["region"]
    return {
        "lambda":   boto3.client("lambda",   region_name=region),
        "dynamodb": boto3.resource("dynamodb", region_name=region),
        "connect":  boto3.client("connect",  region_name=region),
        "sqs":      boto3.client("sqs",      region_name=region),
        "s3":       boto3.client("s3",       region_name=region),
    }


class TestLambdaFunctions:

    def test_ivr_handler_invocable(self, aws_clients, config):
        """IVR handler Lambda should respond to a mock Connect event."""
        client = aws_clients["lambda"]
        fn     = f"{config['prefix']}-ivr-handler"

        payload = {
            "ContactId": "smoke-test-001",
            "Details": {
                "ContactData": {
                    "CustomerEndpoint": {"Address": "+910000000000", "Type": "TELEPHONE_NUMBER"},
                    "ContactId": "smoke-test-001",
                },
                "Parameters": {}
            }
        }

        response = client.invoke(
            FunctionName    = fn,
            InvocationType  = "RequestResponse",
            Payload         = json.dumps(payload).encode(),
        )

        assert response["StatusCode"] == 200
        assert "FunctionError" not in response

        result = json.loads(response["Payload"].read())
        assert "CallerType" in result
        assert "GreetingPrompt" in result

    def test_menu_router_invocable(self, aws_clients, config):
        """Menu router should resolve DTMF 1 → BILLING."""
        client = aws_clients["lambda"]
        fn     = f"{config['prefix']}-menu-router"

        payload = {
            "ContactId": "smoke-test-002",
            "Details": {"Parameters": {"DTMFInput": "1", "MenuId": "MAIN_MENU", "RetryCount": "0"}}
        }

        response = client.invoke(
            FunctionName   = fn,
            InvocationType = "RequestResponse",
            Payload        = json.dumps(payload).encode(),
        )

        assert response["StatusCode"] == 200
        result = json.loads(response["Payload"].read())
        assert result.get("Intent") == "BILLING"
        assert result.get("Action") in ["QUEUE", "TRANSFER"]

    def test_crm_lookup_invocable(self, aws_clients, config):
        """CRM lookup should return a valid response for an unknown number."""
        client = aws_clients["lambda"]
        fn     = f"{config['prefix']}-crm-lookup"

        payload = {
            "ContactId": "smoke-test-003",
            "Details": {"Parameters": {"PhoneNumber": "+910000000001"}}
        }

        response = client.invoke(
            FunctionName   = fn,
            InvocationType = "RequestResponse",
            Payload        = json.dumps(payload).encode(),
        )

        assert response["StatusCode"] == 200
        result = json.loads(response["Payload"].read())
        assert "Found" in result


class TestDynamoDBTables:

    def test_menu_config_seeded(self, aws_clients, config):
        """MenuConfig table should have the MAIN_MENU seed item."""
        table = aws_clients["dynamodb"].Table(f"{config['prefix']}-MenuConfig")
        response = table.get_item(Key={"MenuId": "MAIN_MENU", "Version": "v1"})
        item = response.get("Item")
        assert item is not None, "MAIN_MENU seed item not found in MenuConfig table"
        assert "Options" in item


class TestConnectInstance:

    def test_connect_instance_active(self, aws_clients, config):
        """Amazon Connect instance should be ACTIVE."""
        client   = aws_clients["connect"]
        response = client.list_instances()
        instances = [
            i for i in response["InstanceSummaryList"]
            if config["prefix"] in i.get("InstanceAlias", "")
        ]
        assert len(instances) > 0, "No matching Connect instance found"
        assert instances[0]["InstanceStatus"] == "ACTIVE"


class TestS3Buckets:

    def test_audio_bucket_exists(self, aws_clients, config):
        """Audio prompts S3 bucket should be accessible."""
        s3     = aws_clients["s3"]
        bucket = f"{config['prefix']}-audio-prompts"
        response = s3.head_bucket(Bucket=bucket)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
