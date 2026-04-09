"""
lambda/crm-lookup/handler.py
─────────────────────────────
Caller identification: DynamoDB primary source,
external CRM REST API as secondary fallback.
Also serves as API Gateway Lambda proxy endpoint for
external webhook callers (/caller?phone=+91XXXXXXXXXX).
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

dynamodb        = boto3.resource("dynamodb", region_name=os.environ["REGION"])
caller_profiles = dynamodb.Table(os.environ["CALLER_PROFILES_TABLE"])
secrets_client  = boto3.client("secretsmanager", region_name=os.environ["REGION"])

CRM_API_ENDPOINT = os.environ.get("CRM_API_ENDPOINT", "")
CACHE_TTL        = 300  # seconds — in-memory Lambda cache


# ── In-memory short-circuit cache (survives warm invocations) ─
_profile_cache: dict = {}


def lambda_handler(event: dict, context) -> dict:
    """
    Handles two invocation patterns:
      1. Amazon Connect flow → event has "ContactId" key
      2. API Gateway proxy  → event has "httpMethod" key
    """
    if "httpMethod" in event:
        return _handle_api_gateway(event)
    return _handle_connect(event)


# ── Connect invocation ────────────────────────────────────────

def _handle_connect(event: dict) -> dict:
    contact_id   = event.get("ContactId", "unknown")
    params       = event.get("Details", {}).get("Parameters", {})
    phone_number = params.get("PhoneNumber", "")

    logger.info("CRM Lookup (Connect) | ContactId=%s | Phone=%s",
                contact_id, phone_number)

    profile = _lookup_profile(phone_number)

    return {
        "Found":          "TRUE" if profile else "FALSE",
        "CustomerId":     profile.get("CustomerId", ""),
        "CustomerName":   profile.get("Name", ""),
        "AccountStatus":  profile.get("AccountStatus", "ACTIVE"),
        "CRMSource":      profile.get("_source", "NONE"),
        "Language":       profile.get("PreferredLanguage", "en-IN"),
        "VIP":            str(profile.get("VIP", False)).upper(),
    }


# ── API Gateway invocation ────────────────────────────────────

def _handle_api_gateway(event: dict) -> dict:
    method = event.get("httpMethod", "")
    if method != "GET":
        return _api_response(405, {"error": "Method not allowed"})

    qs     = event.get("queryStringParameters") or {}
    phone  = qs.get("phone", "").strip()

    if not phone:
        return _api_response(400, {"error": "Missing 'phone' query parameter"})

    profile = _lookup_profile(phone)
    if profile:
        return _api_response(200, profile)
    return _api_response(404, {"error": "Caller profile not found"})


def _api_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "X-Service": "ivr-crm-lookup",
        },
        "body": json.dumps(body),
    }


# ── Core lookup logic ─────────────────────────────────────────

def _lookup_profile(phone: str) -> dict:
    """
    1. Check in-memory cache
    2. Query DynamoDB
    3. Fallback to external CRM
    4. Cache result
    """
    if not phone or phone == "UNKNOWN":
        return {}

    # 1. In-memory cache
    cached = _profile_cache.get(phone)
    if cached:
        logger.debug("Cache hit for %s", phone)
        return cached

    # 2. DynamoDB
    profile = _lookup_dynamodb(phone)
    if profile:
        profile["_source"] = "DYNAMODB"
        _profile_cache[phone] = profile
        return profile

    # 3. External CRM
    if CRM_API_ENDPOINT:
        profile = _lookup_crm(phone)
        if profile:
            profile["_source"] = "CRM"
            _upsert_profile(phone, profile)
            _profile_cache[phone] = profile
            return profile

    return {}


def _lookup_dynamodb(phone: str) -> dict:
    try:
        response = caller_profiles.get_item(Key={"PhoneNumber": phone})
        return response.get("Item", {})
    except ClientError as exc:
        logger.error("DynamoDB lookup error: %s", exc)
        return {}


def _lookup_crm(phone: str) -> dict:
    """Call external CRM REST endpoint."""
    url = f"{CRM_API_ENDPOINT}/caller?phone={phone}"
    try:
        api_key = _get_crm_api_key()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            logger.info("CRM lookup success for %s", phone)
            return _normalise_crm_profile(data)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            logger.info("CRM: caller not found for %s", phone)
        else:
            logger.warning("CRM HTTP error %s for %s", exc.code, phone)
        return {}
    except Exception as exc:
        logger.warning("CRM lookup failed: %s", exc)
        return {}


def _get_crm_api_key() -> str:
    """Retrieve CRM API key from Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(
            SecretId=f"{os.environ.get('ENVIRONMENT','prod')}/ivr/crm-api-key"
        )
        return response["SecretString"]
    except ClientError:
        return ""


def _normalise_crm_profile(raw: dict) -> dict:
    """Map external CRM fields to internal schema."""
    return {
        "CustomerId":        raw.get("id", ""),
        "Name":              raw.get("full_name", raw.get("name", "")),
        "AccountStatus":     raw.get("status", "ACTIVE").upper(),
        "PreferredLanguage": raw.get("language", "en-IN"),
        "VIP":               raw.get("vip", False),
        "PreferredQueue":    raw.get("routing_group", "GENERAL"),
    }


def _upsert_profile(phone: str, profile: dict) -> None:
    """Cache a CRM-sourced profile in DynamoDB for future calls."""
    try:
        item = {**profile, "PhoneNumber": phone,
                "CreatedAt": datetime.now(timezone.utc).isoformat()}
        item.pop("_source", None)
        caller_profiles.put_item(Item=item)
        logger.info("Cached CRM profile in DynamoDB for %s", phone)
    except ClientError as exc:
        logger.warning("Failed to cache CRM profile: %s", exc)
