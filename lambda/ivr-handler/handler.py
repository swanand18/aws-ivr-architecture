"""
lambda/ivr-handler/handler.py
────────────────────────────
Main IVR entry-point invoked by Amazon Connect.
Handles inbound contact events, identifies the caller,
and returns routing decisions + dynamic prompts.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# ── Logging ───────────────────────────────────────────────────
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ── AWS Clients ───────────────────────────────────────────────
dynamodb = boto3.resource("dynamodb", region_name=os.environ["REGION"])
caller_profiles = dynamodb.Table(os.environ["CALLER_PROFILES_TABLE"])
call_logs       = dynamodb.Table(os.environ["CALL_LOGS_TABLE"])

# ── Constants ─────────────────────────────────────────────────
DEFAULT_LANGUAGE   = "en-IN"
CALL_LOG_TTL_DAYS  = 90


def lambda_handler(event: dict, context) -> dict:
    """
    Entry point for Amazon Connect contact flow invocation.

    Parameters
    ----------
    event : dict
        Connect contact flow event containing ContactData, Parameters, etc.
    context : LambdaContext

    Returns
    -------
    dict
        Response consumed by Connect contact flow attributes.
    """
    logger.info("IVR Handler invoked | ContactId=%s",
                event.get("ContactId", "unknown"))
    logger.debug("Event payload: %s", json.dumps(event))

    contact_id   = event.get("ContactId", str(uuid.uuid4()))
    contact_data = event.get("Details", {}).get("ContactData", {})
    caller_number = _get_caller_number(contact_data)

    try:
        # 1. Identify caller
        profile = _get_caller_profile(caller_number)

        # 2. Log the call
        _log_call(contact_id, caller_number, profile)

        # 3. Build response attributes
        response = _build_response(profile, contact_data)

        logger.info("IVR Handler success | ContactId=%s | CallerType=%s",
                    contact_id, response.get("CallerType", "UNKNOWN"))
        return response

    except Exception as exc:
        logger.exception("IVR Handler error | ContactId=%s | Error=%s",
                         contact_id, str(exc))
        # Always return a safe fallback so Connect flow doesn't break
        return _fallback_response()


# ── Private helpers ────────────────────────────────────────────

def _get_caller_number(contact_data: dict) -> str:
    """Extract caller ANI from Connect contact data."""
    customer_endpoint = contact_data.get("CustomerEndpoint", {})
    address = customer_endpoint.get("Address", "")
    return address if address else "UNKNOWN"


def _get_caller_profile(phone_number: str) -> dict:
    """Fetch caller profile from DynamoDB. Returns empty dict if not found."""
    if phone_number == "UNKNOWN":
        return {}

    try:
        response = caller_profiles.get_item(
            Key={"PhoneNumber": phone_number}
        )
        profile = response.get("Item", {})
        if profile:
            logger.info("Caller profile found | Phone=%s | CustomerId=%s",
                        phone_number, profile.get("CustomerId", "N/A"))
        else:
            logger.info("No profile for %s — treating as new caller", phone_number)
        return profile

    except ClientError as exc:
        logger.error("DynamoDB error fetching profile: %s", exc)
        return {}


def _log_call(contact_id: str, phone_number: str, profile: dict) -> None:
    """Write call log entry to DynamoDB."""
    now = datetime.now(timezone.utc)
    ttl = int(time.time()) + (CALL_LOG_TTL_DAYS * 86400)

    try:
        call_logs.put_item(Item={
            "ContactId":   contact_id,
            "Timestamp":   now.isoformat(),
            "PhoneNumber": phone_number,
            "CustomerId":  profile.get("CustomerId", ""),
            "CustomerName": profile.get("Name", ""),
            "Status":      "INITIATED",
            "Environment": os.environ.get("ENVIRONMENT", "unknown"),
            "ExpiresAt":   ttl,
        })
    except ClientError as exc:
        # Non-fatal — log and continue
        logger.warning("Failed to write call log: %s", exc)


def _build_response(profile: dict, contact_data: dict) -> dict:
    """Build Connect contact flow attribute response."""
    is_returning = bool(profile)
    caller_type  = "RETURNING" if is_returning else "NEW"
    language     = profile.get("PreferredLanguage", DEFAULT_LANGUAGE)
    vip          = str(profile.get("VIP", False)).upper()

    return {
        "CallerType":     caller_type,
        "CustomerId":     profile.get("CustomerId", ""),
        "CustomerName":   profile.get("Name", ""),
        "Language":       language,
        "VIP":            vip,
        "AccountStatus":  profile.get("AccountStatus", "ACTIVE"),
        "PreferredQueue": profile.get("PreferredQueue", "GENERAL"),
        "GreetingPrompt": _select_greeting(caller_type, profile),
        "LastCallDate":   profile.get("LastCallDate", ""),
    }


def _select_greeting(caller_type: str, profile: dict) -> str:
    """Select appropriate S3 prompt key based on caller history."""
    if caller_type == "RETURNING" and profile.get("VIP"):
        return "prompts/greeting-vip.mp3"
    if caller_type == "RETURNING":
        return "prompts/greeting-returning.mp3"
    return "prompts/greeting-new.mp3"


def _fallback_response() -> dict:
    """Safe fallback if anything goes wrong — Connect flow will use defaults."""
    return {
        "CallerType":     "UNKNOWN",
        "CustomerId":     "",
        "CustomerName":   "",
        "Language":       DEFAULT_LANGUAGE,
        "VIP":            "FALSE",
        "AccountStatus":  "ACTIVE",
        "PreferredQueue": "GENERAL",
        "GreetingPrompt": "prompts/greeting-new.mp3",
        "LastCallDate":   "",
    }
