import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from .database import supabase
from .config import settings

logger = logging.getLogger(__name__)

# Fixed hash used by the frontend when it runs outside Telegram (local dev).
DEV_HASH = "1234567890abcdefghijklmnopqrstuvwxyz1234"
DEV_TELEGRAM_ID = 278423846


def _get_or_create_user(telegram_user_id: int) -> str:
    """Return the internal users.id for a Telegram user, creating the row if needed."""
    res = (
        supabase.table("users")
        .select("id")
        .eq("telegram_user_id", telegram_user_id)
        .execute()
    )
    if res.data:
        return res.data[0]["id"]
    created = (
        supabase.table("users")
        .insert({"telegram_user_id": telegram_user_id})
        .execute()
    )
    return created.data[0]["id"]


def _verify_init_data(init_data: str) -> dict:
    """Validate Telegram Mini App initData and return the parsed fields.

    Telegram sends initData as a urlencoded query string. Values MUST be
    percent-decoded before building the data-check-string, otherwise the
    signature never matches. parse_qsl handles that decoding for us.
    """
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="No hash in initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(
        b"WebAppData", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid Telegram signature")

    return pairs


async def get_current_user(
    telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
) -> str:
    # Local-dev bypass: only when explicitly enabled and using the known dev hash.
    if settings.ALLOW_DEV_LOGIN and f"hash={DEV_HASH}" in telegram_init_data:
        return _get_or_create_user(DEV_TELEGRAM_ID)

    try:
        pairs = _verify_init_data(telegram_init_data)
        user_data = json.loads(pairs.get("user", "{}"))
        telegram_user_id = user_data.get("id")
        if not telegram_user_id:
            raise HTTPException(status_code=401, detail="User ID not found in initData")
        return _get_or_create_user(telegram_user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Auth error")
        raise HTTPException(status_code=401, detail=f"Auth error: {str(e)}")
