"""
tests/unit/test_recording_processor.py
"""
import importlib.util
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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

SAMPLE_CONTACT_ID = "12345678-1234-1234-1234-123456789abc"
SAMPLE_KEY = (
    f"connect-recordings/instance-id/CallRecordings/2024/04/01/"
    f"{SAMPLE_CONTACT_ID}_20240401T120000Z.wav"
)


def _load_handler():
    for key in [k for k in sys.modules if "recording" in k]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        "recording_processor",
        os.path.join(os.path.dirname(__file__), "../../lambda/recording-processor/handler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _s3_event(bucket: str, key: str, size: int = 512000) -> dict:
    return {
        "Records": [{
            "eventVersion": "2.1",
            "eventSource": "aws:s3",
            "awsRegion": "ap-south-1",
            "eventName": "ObjectCreated:Put",
            "s3": {
                "bucket": {"name": bucket},
                "object": {"key": key, "size": size},
            },
        }]
    }


@mock_aws
class TestRecordingProcessor(unittest.TestCase):

    def setUp(self):
        # S3
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.create_bucket(
            Bucket="test-recordings",
            CreateBucketConfiguration={"LocationConstraint": "ap-south-1"},
        )
        s3.put_object(Bucket="test-recordings", Key=SAMPLE_KEY, Body=b"fake-wav-data")

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

    def test_extract_contact_id_from_key(self):
        mod = _load_handler()
        contact_id = mod._extract_contact_id(SAMPLE_KEY)
        self.assertEqual(contact_id, SAMPLE_CONTACT_ID)

    def test_non_wav_file_skipped(self):
        mod   = _load_handler()
        event = _s3_event("test-recordings", "connect-recordings/some-file.mp3")
        result = mod.lambda_handler(event, None)
        self.assertEqual(result["results"][0]["status"], "SKIPPED")

    def test_s3_tagging_applied(self):
        mod = _load_handler()

        with patch.object(mod.transcribe, "start_transcription_job", return_value={}):
            event  = _s3_event("test-recordings", SAMPLE_KEY)
            result = mod.lambda_handler(event, None)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["results"][0]["contactId"], SAMPLE_CONTACT_ID)

        # Verify S3 tag was applied
        s3   = boto3.client("s3", region_name="ap-south-1")
        tags = s3.get_object_tagging(Bucket="test-recordings", Key=SAMPLE_KEY)
        tag_map = {t["Key"]: t["Value"] for t in tags["TagSet"]}
        self.assertEqual(tag_map["ContactId"], SAMPLE_CONTACT_ID)
        self.assertEqual(tag_map["Processed"], "true")

    def test_transcription_job_started(self):
        mod = _load_handler()
        started_jobs = []

        def fake_start(TranscriptionJobName, **kwargs):
            started_jobs.append(TranscriptionJobName)
            return {}

        with patch.object(mod.transcribe, "start_transcription_job", side_effect=fake_start):
            event = _s3_event("test-recordings", SAMPLE_KEY)
            mod.lambda_handler(event, None)

        self.assertEqual(len(started_jobs), 1)
        self.assertIn(SAMPLE_CONTACT_ID[:8], started_jobs[0])

    def test_multiple_records_processed(self):
        mod = _load_handler()
        key2 = SAMPLE_KEY.replace(SAMPLE_CONTACT_ID, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        s3 = boto3.client("s3", region_name="ap-south-1")
        s3.put_object(Bucket="test-recordings", Key=key2, Body=b"fake")

        event = {
            "Records": [
                _s3_event("test-recordings", SAMPLE_KEY)["Records"][0],
                _s3_event("test-recordings", key2)["Records"][0],
            ]
        }

        with patch.object(mod.transcribe, "start_transcription_job", return_value={}):
            result = mod.lambda_handler(event, None)

        self.assertEqual(result["processed"], 2)


if __name__ == "__main__":
    unittest.main()
