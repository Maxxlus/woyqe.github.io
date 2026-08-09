"""Chat/message synchronisation + background poller.

Pulls real conversations and messages from the connectors into Supabase.
The frontend subscribes to the `messages` table via Supabase Realtime, so any
NEW row we insert here shows up instantly without a manual refresh.
"""

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from ..config import settings
from ..connectors.base import ConnectorError
from ..connectors.instagram import InstagramConnector
from ..connectors.max import MaxConnector
from ..connectors.vk import VKConnector
from ..database import supabase

logger = logging.getLogger(__name__)

CONNECTORS = {
    "instagram": InstagramConnector,
    "max": MaxConnector,
    "vk": VKConnector,
}


def _connector(platform: str):
    return CONNECTORS[platform]()


def _upsert_chat(account: Dict[str, Any], chat: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Insert or update a chat. Returns (row, changed) where changed means the
    last message advanced (used by the poller to decide whether to pull messages)."""
    existing = (
        supabase.table("chats")
        .select("id, last_message_at")
        .eq("account_id", account["id"])
        .eq("external_chat_id", chat["external_chat_id"])
        .execute()
    )
    row_data = {
        "account_id": account["id"],
        "platform": account["platform"],
        "external_chat_id": chat["external_chat_id"],
        "title": chat.get("title"),
        "avatar_url": chat.get("avatar_url"),
        "last_message_text": chat.get("last_message_text"),
        "last_message_at": chat.get("last_message_at"),
        "unread_count": chat.get("unread_count", 0),
    }
    if existing.data:
        prev = existing.data[0]
        changed = str(prev.get("last_message_at")) != str(chat.get("last_message_at"))
        res = supabase.table("chats").update(row_data).eq("id", prev["id"]).execute()
        return res.data[0], changed
    res = supabase.table("chats").insert(row_data).execute()
    return res.data[0], True


async def sync_account_chats(account: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch chats from the messenger and persist them. Returns stored rows."""
    connector = _connector(account["platform"])
    remote = await connector.get_chats(account)
    rows = []
    for chat in remote:
        row, _ = _upsert_chat(account, chat)
        rows.append(row)
    return rows


async def sync_chat_messages(account: Dict[str, Any], chat: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fetch a chat's messages, insert the ones we don't have yet. Returns new rows."""
    connector = _connector(account["platform"])
    remote = await connector.get_messages(account, chat["external_chat_id"])
    if not remote:
        return []

    existing = (
        supabase.table("messages")
        .select("external_message_id")
        .eq("chat_id", chat["id"])
        .execute()
    )
    seen = {m["external_message_id"] for m in (existing.data or [])}

    new_rows = []
    for m in remote:
        if m["external_message_id"] in seen:
            continue
        payload = {
            "chat_id": chat["id"],
            "platform": account["platform"],
            "external_message_id": m["external_message_id"],
            "sender_id": m.get("sender_id"),
            "sender_name": m.get("sender_name"),
            "text": m.get("text"),
            "direction": m.get("direction"),
            "status": "delivered",
        }
        if m.get("created_at"):
            payload["created_at"] = m["created_at"]
        try:
            res = supabase.table("messages").insert(payload).execute()
            if res.data:
                new_rows.append(res.data[0])
        except Exception as e:  # noqa: BLE001 - unique-constraint race: message already stored
            logger.debug("[SYNC] skip duplicate message %s: %s", m["external_message_id"], e)

    last = remote[-1]
    supabase.table("chats").update({
        "last_message_text": (last.get("text") or "")[:120],
        "last_message_at": last.get("created_at"),
    }).eq("id", chat["id"]).execute()

    return new_rows


def _mark_account_error_if_expired(account: Dict[str, Any], err: Exception) -> None:
    if "session" in str(err).lower() or "expired" in str(err).lower():
        supabase.table("accounts").update({"status": "error"}).eq("id", account["id"]).execute()
        logger.warning("[POLL] Marked account %s as error: %s", account["id"], err)


async def _poll_once() -> None:
    accounts = (
        supabase.table("accounts")
        .select("*")
        .eq("status", "connected")
        .execute()
    )
    for account in accounts.data or []:
        if account["platform"] not in CONNECTORS:
            continue
        try:
            connector = _connector(account["platform"])
            remote_chats = await connector.get_chats(account)
        except ConnectorError as e:
            _mark_account_error_if_expired(account, e)
            continue
        except Exception:  # noqa: BLE001
            logger.exception("[POLL] get_chats failed for %s", account["id"])
            continue

        for chat in remote_chats:
            row, changed = _upsert_chat(account, chat)
            if not changed:
                continue
            try:
                await sync_chat_messages(account, row)
            except ConnectorError as e:
                _mark_account_error_if_expired(account, e)
            except Exception:  # noqa: BLE001
                logger.exception("[POLL] sync_chat_messages failed for chat %s", row.get("id"))


async def poll_loop() -> None:
    """Background loop: pull new incoming messages on an interval."""
    interval = max(15, settings.POLL_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(interval)
            await _poll_once()
        except asyncio.CancelledError:
            logger.info("[POLL] stopped")
            break
        except Exception:  # noqa: BLE001
            logger.exception("[POLL] loop iteration failed")
