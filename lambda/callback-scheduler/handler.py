"""
lambda/callback-scheduler/handler.py
──────────────────────────────────────
Receives a callback request from Connect contact flow
and enqueues it to SQS for asynchronous processing.
Also handles SQS consumer logic for executing callbacks
via Amazon Connect outbound campaigns.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

sqs          = boto3.client("sqs",      region_name=os.environ["REGION"])
connect      = boto3.client("connect",  region_name=os.environ["REGION"])
dynamodb     = boto3.resource("dynamodb", region_name=os.environ["REGION"])
call_logs    = dynamodb.Table(os.environ["CALL_LOGS_TABLE"])

QUEUE_URL    = os.environ["CALLBACK_QUEUE_URL"]
ENVIRONMENT  = os.environ.get("ENVIRONMENT", "prod")


def lambda_handler(event: dict, context) -> dict:
    """
    Dual-mode handler:
      • Connect flow → schedule a callback (SQS enqueue)
      • SQS trigger  → execute pending callbacks (outbound dial)
    """
    if "Records" in event:
        return _process_sqs_records(event["Records"])
    return _schedule_callback(event)


# ── Schedule a callback (Connect → SQS) ──────────────────────

def _schedule_callback(event: dict) -> dict:
    contact_id = event.get("ContactId", "unknown")
    params     = event.get("Details", {}).get("Parameters", {})

    phone_number    = params.get("PhoneNumber", "")
    customer_name   = params.get("CustomerName", "")
    preferred_time  = params.get("PreferredTime", "ASAP")
    intent          = params.get("Intent", "GENERAL")

    if not phone_number:
        logger.error("No PhoneNumber in callback request | ContactId=%s", contact_id)
        return {"Status": "ERROR", "Message": "Phone number required"}

    callback_id = str(uuid.uuid4())
    payload = {
        "CallbackId":    callback_id,
        "ContactId":     contact_id,
        "PhoneNumber":   phone_number,
        "CustomerName":  customer_name,
        "PreferredTime": preferred_time,
        "Intent":        intent,
        "ScheduledAt":   datetime.now(timezone.utc).isoformat(),
        "Environment":   ENVIRONMENT,
        "Attempts":      0,
    }

    try:
        sqs.send_message(
            QueueUrl    = QUEUE_URL,
            MessageBody = json.dumps(payload),
            MessageGroupId      = phone_number.replace("+", ""),  # for FIFO queues
            MessageDeduplicationId = callback_id,
        )
        logger.info("Callback scheduled | CallbackId=%s | Phone=%s",
                    callback_id, phone_number)

        _log_callback(contact_id, callback_id, phone_number)

        return {
            "Status":     "SCHEDULED",
            "CallbackId": callback_id,
            "Message":    "Callback queued successfully",
        }

    except ClientError as exc:
        logger.exception("Failed to queue callback: %s", exc)
        return {"Status": "ERROR", "Message": str(exc)}


# ── Process SQS callbacks (Execute outbound dial) ─────────────

def _process_sqs_records(records: list) -> dict:
    results = {"processed": 0, "failed": 0}

    for record in records:
        try:
            payload = json.loads(record["body"])
            _execute_callback(payload)
            results["processed"] += 1
        except Exception as exc:
            logger.exception("Failed to process SQS record: %s", exc)
            results["failed"] += 1

    logger.info("SQS batch complete | Processed=%d | Failed=%d",
                results["processed"], results["failed"])
    return results


def _execute_callback(payload: dict) -> None:
    """Initiate outbound call via Amazon Connect."""
    callback_id  = payload["CallbackId"]
    phone_number = payload["PhoneNumber"]

    # Retrieve Connect instance ID and contact flow ARN from env/SSM
    instance_id      = os.environ.get("CONNECT_INSTANCE_ID", "")
    contact_flow_id  = os.environ.get("CALLBACK_CONTACT_FLOW_ID", "")
    source_number    = os.environ.get("CONNECT_SOURCE_NUMBER", "")

    if not all([instance_id, contact_flow_id, source_number]):
        logger.warning("Connect config missing — skipping outbound for %s", callback_id)
        return

    try:
        response = connect.start_outbound_voice_contact(
            DestinationPhoneNumber = phone_number,
            ContactFlowId          = contact_flow_id,
            InstanceId             = instance_id,
            SourcePhoneNumber      = source_number,
            Attributes             = {
                "CallbackId":    callback_id,
                "CustomerName":  payload.get("CustomerName", ""),
                "Intent":        payload.get("Intent", "GENERAL"),
                "IsCallback":    "true",
            },
        )
        logger.info("Outbound call initiated | CallbackId=%s | ContactId=%s",
                    callback_id, response["ContactId"])

    except connect.exceptions.LimitExceededException:
        logger.warning("Connect rate limit hit — callback will retry | %s", callback_id)
        raise  # Let SQS retry
    except ClientError as exc:
        logger.error("Failed to initiate outbound call: %s", exc)
        raise


def _log_callback(contact_id: str, callback_id: str, phone: str) -> None:
    try:
        call_logs.update_item(
            Key={"ContactId": contact_id, "Timestamp": _latest_ts(contact_id)},
            UpdateExpression="SET CallbackId = :cb, CallbackStatus = :st, UpdatedAt = :ts",
            ExpressionAttributeValues={
                ":cb": callback_id,
                ":st": "QUEUED",
                ":ts": datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError:
        pass


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
