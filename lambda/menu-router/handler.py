"""
lambda/menu-router/handler.py
─────────────────────────────
DTMF / speech-intent routing engine.
Loads menu config from DynamoDB and returns next routing action
based on caller input key.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb   = boto3.resource("dynamodb", region_name=os.environ["REGION"])
menu_table = dynamodb.Table(os.environ["MENU_CONFIG_TABLE"])
logs_table = dynamodb.Table(os.environ["CALL_LOGS_TABLE"])

# ── Intent → Queue / Transfer target map ─────────────────────
INTENT_ROUTING = {
    "BILLING":   {"action": "QUEUE",    "target": "BillingQueue",   "prompt": "prompts/routing-billing.mp3"},
    "SUPPORT":   {"action": "QUEUE",    "target": "SupportQueue",   "prompt": "prompts/routing-support.mp3"},
    "SALES":     {"action": "QUEUE",    "target": "SalesQueue",     "prompt": "prompts/routing-sales.mp3"},
    "OPERATOR":  {"action": "TRANSFER", "target": "OperatorQueue",  "prompt": "prompts/routing-operator.mp3"},
    "CALLBACK":  {"action": "CALLBACK", "target": "CallbackFlow",   "prompt": "prompts/routing-callback.mp3"},
    "INVALID":   {"action": "REPROMPT", "target": "",               "prompt": "prompts/invalid-input.mp3"},
    "TIMEOUT":   {"action": "REPROMPT", "target": "",               "prompt": "prompts/timeout.mp3"},
}

MAX_RETRIES = 3


def lambda_handler(event: dict, context) -> dict:
    logger.info("Menu Router invoked | ContactId=%s",
                event.get("ContactId", "unknown"))

    contact_id   = event.get("ContactId", "unknown")
    params       = event.get("Details", {}).get("Parameters", {})
    dtmf_input   = params.get("DTMFInput", "").strip()
    menu_id      = params.get("MenuId", "MAIN_MENU")
    retry_count  = int(params.get("RetryCount", "0"))

    try:
        menu_config = _load_menu(menu_id)
        intent      = _resolve_intent(dtmf_input, menu_config)
        routing     = _get_routing(intent, retry_count, menu_config)

        _update_call_log(contact_id, intent, dtmf_input)

        logger.info("Routing decision | ContactId=%s | DTMF=%s | Intent=%s | Action=%s",
                    contact_id, dtmf_input, intent, routing["Action"])
        return routing

    except Exception as exc:
        logger.exception("Menu Router error: %s", exc)
        return {
            "Action":       "REPROMPT",
            "Target":       "",
            "Prompt":       "prompts/system-error.mp3",
            "Intent":       "ERROR",
            "RetryCount":   str(retry_count),
            "EndCall":      "FALSE",
        }


def _load_menu(menu_id: str) -> dict:
    """Load menu config from DynamoDB (latest active version)."""
    try:
        response = menu_table.get_item(
            Key={"MenuId": menu_id, "Version": "v1"}
        )
        item = response.get("Item")
        if not item:
            logger.warning("Menu config not found for %s — using defaults", menu_id)
            return _default_menu()
        return item
    except ClientError as exc:
        logger.error("Failed to load menu config: %s", exc)
        return _default_menu()


def _default_menu() -> dict:
    return {
        "Options": {"1": "BILLING", "2": "SUPPORT", "3": "SALES",
                    "0": "OPERATOR", "9": "CALLBACK"},
        "MaxRetries": 3,
    }


def _resolve_intent(dtmf: str, menu: dict) -> str:
    """Map DTMF digit to intent string."""
    if not dtmf:
        return "TIMEOUT"
    options = menu.get("Options", {})
    return options.get(dtmf, "INVALID")


def _get_routing(intent: str, retry_count: int, menu: dict) -> dict:
    max_retries = int(menu.get("MaxRetries", MAX_RETRIES))
    routing_def = INTENT_ROUTING.get(intent, INTENT_ROUTING["INVALID"])

    should_end = (
        routing_def["action"] == "REPROMPT" and retry_count >= max_retries
    )

    return {
        "Action":     "HANGUP" if should_end else routing_def["action"],
        "Target":     routing_def["target"],
        "Prompt":     "prompts/max-retries.mp3" if should_end else routing_def["prompt"],
        "Intent":     intent,
        "RetryCount": str(retry_count + 1),
        "EndCall":    "TRUE" if should_end else "FALSE",
    }


def _update_call_log(contact_id: str, intent: str, dtmf: str) -> None:
    try:
        logs_table.update_item(
            Key={"ContactId": contact_id, "Timestamp": _latest_log_timestamp(contact_id)},
            UpdateExpression="SET MenuIntent = :intent, DTMFInput = :dtmf, UpdatedAt = :ts",
            ExpressionAttributeValues={
                ":intent": intent,
                ":dtmf":   dtmf,
                ":ts":     datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError:
        pass  # Non-fatal


def _latest_log_timestamp(contact_id: str) -> str:
    """Lookup most recent log entry timestamp for a contact (best-effort)."""
    try:
        response = logs_table.query(
            KeyConditionExpression="ContactId = :cid",
            ExpressionAttributeValues={":cid": contact_id},
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0]["Timestamp"] if items else ""
    except Exception:
        return ""
