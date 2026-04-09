"""
tests/unit/test_ivr_handler.py
"""
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

# ── Set required env vars BEFORE importing handler ────────────
os.environ.update({
    "REGION":                 "ap-south-1",
    "CALLER_PROFILES_TABLE":  "test-CallerProfiles",
    "MENU_CONFIG_TABLE":      "test-MenuConfig",
    "CALL_LOGS_TABLE":        "test-CallLogs",
    "AUDIO_BUCKET":           "test-audio",
    "RECORDINGS_BUCKET":      "test-recordings",
    "CALLBACK_QUEUE_URL":     "https://sqs.ap-south-1.amazonaws.com/123/test-queue",
    "ALERT_TOPIC_ARN":        "arn:aws:sns:ap-south-1:123:test-topic",
    "ENVIRONMENT":            "test",
    "LOG_LEVEL":              "DEBUG",
})


def _create_tables(dynamodb):
    """Helper — create DynamoDB tables required by ivr-handler."""
    dynamodb.create_table(
        TableName="test-CallerProfiles",
        KeySchema=[{"AttributeName": "PhoneNumber", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "PhoneNumber", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb.create_table(
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


def _connect_event(phone: str = "+919876543210", contact_id: str = "test-contact-001") -> dict:
    return {
        "ContactId": contact_id,
        "Details": {
            "ContactData": {
                "CustomerEndpoint": {"Address": phone, "Type": "TELEPHONE_NUMBER"},
                "ContactId": contact_id,
                "Channel": "VOICE",
            },
            "Parameters": {},
        },
    }


@mock_aws
class TestIvrHandler(unittest.TestCase):

    def setUp(self):
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
        _create_tables(self.dynamodb)
        # Import here so moto intercepts boto3 calls
        import importlib
        import sys
        if "handler" in sys.modules:
            del sys.modules["handler"]
        import lambda_loader  # noqa - see conftest

    def _import_handler(self):
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "handler",
            os.path.join(os.path.dirname(__file__), "../../lambda/ivr-handler/handler.py")
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["handler"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_new_caller_returns_correct_attributes(self):
        mod = self._import_handler()
        event = _connect_event("+910000000001", "contact-new")
        result = mod.lambda_handler(event, None)

        self.assertEqual(result["CallerType"], "NEW")
        self.assertEqual(result["VIP"], "FALSE")
        self.assertIn("GreetingPrompt", result)
        self.assertEqual(result["GreetingPrompt"], "prompts/greeting-new.mp3")

    def test_returning_caller_profile_loaded(self):
        mod = self._import_handler()
        # Pre-seed a profile
        table = self.dynamodb.Table("test-CallerProfiles")
        table.put_item(Item={
            "PhoneNumber":  "+919876543210",
            "CustomerId":   "CUST-001",
            "Name":         "Swanand Awatade",
            "AccountStatus": "ACTIVE",
            "VIP":          False,
            "PreferredLanguage": "en-IN",
        })

        event  = _connect_event("+919876543210", "contact-returning")
        result = mod.lambda_handler(event, None)

        self.assertEqual(result["CallerType"], "RETURNING")
        self.assertEqual(result["CustomerId"], "CUST-001")
        self.assertEqual(result["CustomerName"], "Swanand Awatade")

    def test_vip_caller_returns_vip_greeting(self):
        mod = self._import_handler()
        table = self.dynamodb.Table("test-CallerProfiles")
        table.put_item(Item={
            "PhoneNumber": "+911111111111",
            "CustomerId":  "CUST-VIP-001",
            "Name":        "VIP Customer",
            "VIP":         True,
            "AccountStatus": "ACTIVE",
        })

        event  = _connect_event("+911111111111", "contact-vip")
        result = mod.lambda_handler(event, None)

        self.assertEqual(result["VIP"], "TRUE")
        self.assertEqual(result["GreetingPrompt"], "prompts/greeting-vip.mp3")

    def test_unknown_caller_returns_fallback(self):
        mod = self._import_handler()
        event = _connect_event("UNKNOWN", "contact-unknown")
        result = mod.lambda_handler(event, None)

        self.assertEqual(result["CallerType"], "NEW")
        self.assertIsNotNone(result.get("GreetingPrompt"))

    def test_dynamodb_error_returns_fallback(self):
        mod = self._import_handler()
        with patch.object(mod.caller_profiles, "get_item",
                          side_effect=Exception("DynamoDB down")):
            event  = _connect_event("+919999999999", "contact-error")
            result = mod.lambda_handler(event, None)

        # Should not raise — should return safe fallback
        self.assertIn("CallerType", result)
        self.assertIn("GreetingPrompt", result)

    def test_call_log_written(self):
        mod = self._import_handler()
        event = _connect_event("+912222222222", "contact-log-test")
        mod.lambda_handler(event, None)

        logs_table = self.dynamodb.Table("test-CallLogs")
        response   = logs_table.query(
            KeyConditionExpression="ContactId = :cid",
            ExpressionAttributeValues={":cid": "contact-log-test"},
        )
        self.assertGreater(len(response["Items"]), 0)
        self.assertEqual(response["Items"][0]["Status"], "INITIATED")


if __name__ == "__main__":
    unittest.main()
