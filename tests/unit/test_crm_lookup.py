"""
tests/unit/test_crm_lookup.py
"""
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

os.environ.update({
    "REGION":                "ap-south-1",
    "CALLER_PROFILES_TABLE": "test-CallerProfiles",
    "MENU_CONFIG_TABLE":     "test-MenuConfig",
    "CALL_LOGS_TABLE":       "test-CallLogs",
    "AUDIO_BUCKET":          "test-audio",
    "RECORDINGS_BUCKET":     "test-recordings",
    "CALLBACK_QUEUE_URL":    "https://sqs.ap-south-1.amazonaws.com/123/test",
    "ALERT_TOPIC_ARN":       "arn:aws:sns:ap-south-1:123:test",
    "ENVIRONMENT":           "test",
    "CRM_API_ENDPOINT":      "",
    "LOG_LEVEL":             "DEBUG",
})


def _load_handler():
    for key in [k for k in sys.modules if "crm" in k]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        "crm_lookup",
        os.path.join(os.path.dirname(__file__), "../../lambda/crm-lookup/handler.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _connect_event(phone: str) -> dict:
    return {
        "ContactId": "contact-crm-test",
        "Details": {"Parameters": {"PhoneNumber": phone}},
    }


def _apigw_event(phone: str, method: str = "GET") -> dict:
    return {
        "httpMethod": method,
        "queryStringParameters": {"phone": phone},
        "headers": {},
        "body": None,
    }


@mock_aws
class TestCrmLookup(unittest.TestCase):

    def setUp(self):
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        ddb.create_table(
            TableName="test-CallerProfiles",
            KeySchema=[{"AttributeName": "PhoneNumber", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PhoneNumber", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self.profiles_table = ddb.Table("test-CallerProfiles")

    def test_connect_known_caller_returns_found(self):
        self.profiles_table.put_item(Item={
            "PhoneNumber": "+919876543210",
            "CustomerId":  "CUST-001",
            "Name":        "Swanand",
            "AccountStatus": "ACTIVE",
        })
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("+919876543210"), None)
        self.assertEqual(result["Found"], "TRUE")
        self.assertEqual(result["CustomerId"], "CUST-001")
        self.assertEqual(result["CustomerName"], "Swanand")

    def test_connect_unknown_caller_returns_not_found(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("+910000000000"), None)
        self.assertEqual(result["Found"], "FALSE")
        self.assertEqual(result["CustomerId"], "")

    def test_apigw_get_known_caller(self):
        self.profiles_table.put_item(Item={
            "PhoneNumber": "+911234567890",
            "CustomerId":  "CUST-API-001",
            "Name":        "API Caller",
            "AccountStatus": "ACTIVE",
        })
        mod    = _load_handler()
        result = mod.lambda_handler(_apigw_event("+911234567890"), None)
        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertEqual(body["CustomerId"], "CUST-API-001")

    def test_apigw_get_unknown_caller_returns_404(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_apigw_event("+919999999999"), None)
        self.assertEqual(result["statusCode"], 404)

    def test_apigw_missing_phone_returns_400(self):
        mod    = _load_handler()
        event  = {"httpMethod": "GET", "queryStringParameters": {}}
        result = mod.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 400)

    def test_apigw_wrong_method_returns_405(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_apigw_event("+919999999999", "DELETE"), None)
        self.assertEqual(result["statusCode"], 405)

    def test_unknown_phone_returns_not_found(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("UNKNOWN"), None)
        self.assertEqual(result["Found"], "FALSE")


if __name__ == "__main__":
    unittest.main()
