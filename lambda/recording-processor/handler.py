"""
lambda/recording-processor/handler.py
──────────────────────────────────────
Triggered by S3 ObjectCreated events when Amazon Connect
drops a call recording. Starts an AWS Transcribe job and
updates the call log with recording metadata.
"""

import json
import logging
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

transcribe  = boto3.client("transcribe",  region_name=os.environ["REGION"])
s3          = boto3.client("s3",          region_name=os.environ["REGION"])
dynamodb    = boto3.resource("dynamodb",  region_name=os.environ["REGION"])
call_logs   = dynamodb.Table(os.environ["CALL_LOGS_TABLE"])

RECORDINGS_BUCKET = os.environ["RECORDINGS_BUCKET"]
OUTPUT_BUCKET     = os.environ.get("TRANSCRIPTS_BUCKET", os.environ["RECORDINGS_BUCKET"])
LANGUAGE_CODE     = "en-IN"

# Amazon Connect recording key pattern:
# connect-recordings/<instance-id>/CallRecordings/<year>/<month>/<day>/<contact-id>_<timestamp>.wav
CONTACT_ID_RE = re.compile(r"([0-9a-f-]{36})_\d{8}T\d{6}Z\.wav$")


def lambda_handler(event: dict, context) -> dict:
    results = []
    for record in event.get("Records", []):
        result = _process_record(record)
        results.append(result)
    return {"processed": len(results), "results": results}


def _process_record(record: dict) -> dict:
    bucket = record["s3"]["bucket"]["name"]
    key    = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    size   = record["s3"]["object"]["size"]

    logger.info("Processing recording | Bucket=%s | Key=%s | Size=%d", bucket, key, size)

    if not key.endswith(".wav"):
        logger.info("Skipping non-wav file: %s", key)
        return {"key": key, "status": "SKIPPED"}

    contact_id = _extract_contact_id(key)
    if not contact_id:
        logger.warning("Could not extract ContactId from key: %s", key)
        contact_id = "unknown"

    # 1. Start Transcribe job
    job_name = _start_transcription(bucket, key, contact_id)

    # 2. Tag the S3 object with metadata
    _tag_recording(bucket, key, contact_id)

    # 3. Update DynamoDB call log
    _update_call_log(contact_id, key, job_name)

    return {
        "key":        key,
        "contactId":  contact_id,
        "jobName":    job_name,
        "status":     "TRANSCRIPTION_STARTED",
    }


def _extract_contact_id(key: str) -> str:
    match = CONTACT_ID_RE.search(key)
    return match.group(1) if match else ""


def _start_transcription(bucket: str, key: str, contact_id: str) -> str:
    job_name = f"ivr-{contact_id[:8]}-{int(time.time())}"
    s3_uri   = f"s3://{bucket}/{key}"

    output_key = f"transcripts/{contact_id}.json"

    try:
        transcribe.start_transcription_job(
            TranscriptionJobName = job_name,
            Media                = {"MediaFileUri": s3_uri},
            MediaFormat          = "wav",
            LanguageCode         = LANGUAGE_CODE,
            OutputBucketName     = OUTPUT_BUCKET,
            OutputKey            = output_key,
            Settings             = {
                "ShowSpeakerLabels": True,
                "MaxSpeakerLabels":  2,
                "ChannelIdentification": False,
            },
            Tags = [
                {"Key": "ContactId",   "Value": contact_id},
                {"Key": "Environment", "Value": os.environ.get("ENVIRONMENT", "prod")},
            ],
        )
        logger.info("Transcription job started | Job=%s | ContactId=%s", job_name, contact_id)
        return job_name

    except transcribe.exceptions.ConflictException:
        logger.warning("Transcription job already exists: %s", job_name)
        return job_name
    except ClientError as exc:
        logger.error("Failed to start transcription job: %s", exc)
        return ""


def _tag_recording(bucket: str, key: str, contact_id: str) -> None:
    try:
        s3.put_object_tagging(
            Bucket  = bucket,
            Key     = key,
            Tagging = {
                "TagSet": [
                    {"Key": "ContactId",   "Value": contact_id},
                    {"Key": "Processed",   "Value": "true"},
                    {"Key": "ProcessedAt", "Value": datetime.now(timezone.utc).isoformat()},
                ]
            },
        )
    except ClientError as exc:
        logger.warning("Failed to tag recording: %s", exc)


def _update_call_log(contact_id: str, recording_key: str, job_name: str) -> None:
    if contact_id == "unknown":
        return
    try:
        ts = _latest_ts(contact_id)
        call_logs.update_item(
            Key={"ContactId": contact_id, "Timestamp": ts},
            UpdateExpression=(
                "SET RecordingKey = :rk, TranscribeJob = :tj, "
                "RecordingStatus = :rs, UpdatedAt = :ts"
            ),
            ExpressionAttributeValues={
                ":rk": recording_key,
                ":tj": job_name,
                ":rs": "TRANSCRIPTION_PENDING",
                ":ts": datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError as exc:
        logger.warning("Failed to update call log: %s", exc)


def _latest_ts(contact_id: str) -> str:
    try:
        r = call_logs.query(
            KeyConditionExpression="ContactId = :cid",
            ExpressionAttributeValues={":cid": contact_id},
            ScanIndexForward=False, Limit=1,
        )
        items = r.get("Items", [])
        return items[0]["Timestamp"] if items else datetime.now(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()
