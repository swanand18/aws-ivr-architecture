"""
tests/unit/test_callback_scheduler.py
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
    "CALLBACK_QUEUE_URL":    "https://sqs.ap-south-1.amazonaws.com/123456789/test-callback-queue.fifo",
    "ALERT_TOPIC_ARN":       "arn:aws:sns:ap-south-1:123:test",
    "ENVIRONMENT":           "test",
    "LOG_LEVEL":             "DEBUG",
})


def _load_handler():
    for key in [k for k in sys.modules if "callback" in k]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        "callback_scheduler",
        os.path.join(os.path.dirname(__file__), "../../lambda/callback-scheduler/handler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _connect_event(phone: str = "+919876543210", name: str = "Test Customer") -> dict:
    return {
        "ContactId": "contact-cb-001",
        "Details": {
            "Parameters": {
                "PhoneNumber":   phone,
                "CustomerName":  name,
                "PreferredTime": "ASAP",
                "Intent":        "BILLING",
            }
        },
    }


def _sqs_event(body: dict) -> dict:
    return {
        "Records": [{
            "messageId": "msg-001",
            "body": json.dumps(body),
            "receiptHandle": "handle-001",
        }]
    }


@mock_aws
class TestCallbackScheduler(unittest.TestCase):

    def setUp(self):
        # SQS (standard, not FIFO — moto handles both)
        self.sqs = boto3.client("sqs", region_name="ap-south-1")
        self.queue = self.sqs.create_queue(
            QueueName="test-callback-queue",
        )
        os.environ["CALLBACK_QUEUE_URL"] = self.queue["QueueUrl"]

        # DynamoDB
        ddb = boto3.resource("dynamodb", region_name="ap-south-1")
        ddb.create_table(
            TableName="test-CallLogs",
            KeySchema=[
                {"AttributeName": "ContactId", "KeyType": "HASH"},
                {"AttributeName": "Timestamp",  "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "ContactId", "AttributeType": "S"},
                {"AttributeName": "Timestamp",  "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    def test_schedule_callback_enqueues_message(self):
        mod    = _load_handler()
        result = mod.lambda_handler(_connect_event(), None)

        self.assertEqual(result["Status"], "SCHEDULED")
        self.assertIn("CallbackId", result)
        self.assertTrue(len(result["CallbackId"]) > 0)

        # Verify message in SQS
        msgs = self.sqs.receive_message(
            QueueUrl=self.queue["QueueUrl"],
            MaxNumberOfMessages=1,
        ).get("Messages", [])
        self.assertEqual(len(msgs), 1)

        payload = json.loads(msgs[0]["Body"])
        self.assertEqual(payload["PhoneNumber"], "+919876543210")
        self.assertEqual(payload["Intent"],      "BILLING")

    def test_missing_phone_returns_error(self):
        mod   = _load_handler()
        event = _connect_event(phone="")
        result = mod.lambda_handler(event, None)
        self.assertEqual(result["Status"], "ERROR")

    def test_sqs_trigger_processes_records(self):
        mod = _load_handler()
        payload = {
            "CallbackId":   "cb-001",
            "ContactId":    "contact-cb-002",
            "PhoneNumber":  "+919999999999",
            "CustomerName": "Test",
            "Intent":       "SUPPORT",
            "Attempts":     0,
        }

        # Mock the Connect outbound call
        mock_connect = MagicMock()
        mock_connect.start_outbound_voice_contact.return_value = {"ContactId": "outbound-001"}

        with patch.object(mod, "connect", mock_connect):
            # Set required env for outbound
            os.environ["CONNECT_INSTANCE_ID"]       = "fake-instance-id"
            os.environ["CALLBACK_CONTACT_FLOW_ID"]  = "fake-flow-id"
            os.environ["CONNECT_SOURCE_NUMBER"]     = "+910000000000"

            result = mod.lambda_handler(_sqs_event(payload), None)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"],    0)

    def test_sqs_trigger_handles_malformed_message(self):
        mod   = _load_handler()
        event = {
            "Records": [{
                "messageId": "bad-msg",
                "body": "not-valid-json",
                "receiptHandle": "handle",
            }]
        }
        result = mod.lambda_handler(event, None)
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"],    1)


if __name__ == "__main__":
    unittest.main()
