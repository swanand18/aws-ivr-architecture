"""
tests/unit/test_menu_router.py
"""
import importlib.util
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
    "LOG_LEVEL":             "DEBUG",
})


def _load_handler():
    for key in [k for k in sys.modules if "menu" in k]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        "menu_router",
        os.path.join(os.path.dirname(__file__), "../../lambda/menu-router/handler.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _connect_event(dtmf: str, retry: int = 0, menu_id: str = "MAIN_MENU") -> dict:
    return {
        "ContactId": "test-contact-menu",
        "Details": {
            "Parameters": {
                "DTMFInput":  dtmf,
                "MenuId":     menu_id,
                "RetryCount": str(retry),
            }
        }
    }


@mock_aws
class TestMenuRouter(unittest.TestCase):

    def setUp(self):
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
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
        # Seed menu config
        table = ddb.Table("test-MenuConfig")
        table.put_item(Item={
            "MenuId":  "MAIN_MENU",
            "Version": "v1",
            "Active":  True,
            "Options": {"1": "BILLING", "2": "SUPPORT", "3": "SALES",
                        "0": "OPERATOR", "9": "CALLBACK"},
            "MaxRetries": 3,
        })

    def test_press_1_routes_to_billing(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("1"), None)
        self.assertEqual(result["Intent"], "BILLING")
        self.assertEqual(result["Action"], "QUEUE")
        self.assertIn("billing", result["Target"].lower())

    def test_press_9_routes_to_callback(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("9"), None)
        self.assertEqual(result["Intent"], "CALLBACK")
        self.assertEqual(result["Action"], "CALLBACK")

    def test_invalid_input_reprompts(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("7"), None)
        self.assertEqual(result["Intent"], "INVALID")
        self.assertEqual(result["Action"], "REPROMPT")

    def test_timeout_triggers_reprompt(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event(""), None)
        self.assertEqual(result["Intent"], "TIMEOUT")
        self.assertEqual(result["Action"], "REPROMPT")

    def test_max_retries_ends_call(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("7", retry=3), None)
        self.assertEqual(result["Action"], "HANGUP")
        self.assertEqual(result["EndCall"], "TRUE")

    def test_retry_counter_increments(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("7", retry=1), None)
        self.assertEqual(result["RetryCount"], "2")

    def test_missing_menu_config_uses_defaults(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event("2", menu_id="NONEXISTENT_MENU"), None)
        # Should still resolve SUPPORT from default menu
        self.assertEqual(result["Intent"], "SUPPORT")

    def test_all_dtmf_options(self):
        mod = _load_handler()
        expected = {
            "1": "BILLING", "2": "SUPPORT", "3": "SALES",
            "0": "OPERATOR", "9": "CALLBACK",
        }
        for digit, intent in expected.items():
            with self.subTest(digit=digit):
                result = mod.lambda_handler(_connect_event(digit), None)
                self.assertEqual(result["Intent"], intent)


if __name__ == "__main__":
    unittest.main()
