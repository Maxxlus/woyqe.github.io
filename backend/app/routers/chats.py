from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from ..connectors.base import ConnectorError
from ..database import supabase
from ..dependencies import get_current_user
from ..services import sync

router = APIRouter(prefix="/api/chats", tags=["chats"])


def _connector(platform: str):
    if platform not in sync.CONNECTORS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    return sync.CONNECTORS[platform]()


async def _account_for_chat(chat: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    acc = (
        supabase.table("accounts")
        .select("*")
        .eq("id", chat["account_id"])
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not acc.data:
        raise HTTPException(status_code=403, detail="Not your account")
    return acc.data


@router.get("")
async def get_chats(platform: str | None = None, user_id: str = Depends(get_current_user)):
    query = (
        supabase.table("accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "connected")
    )
    if platform:
        query = query.eq("platform", platform)
    accounts = query.execute()
    if not accounts.data:
        return []

    all_chats = []
    for account in accounts.data:
        try:
            rows = await sync.sync_account_chats(account)
            all_chats.extend(rows)
        except ConnectorError as e:
            # Session likely expired — surface via account status, keep going.
            supabase.table("accounts").update({"status": "error"}).eq("id", account["id"]).execute()
            raise HTTPException(status_code=502, detail=str(e))

    all_chats.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
    return all_chats


@router.get("/{chat_id}/messages")
async def get_messages(chat_id: str, user_id: str = Depends(get_current_user)):
    chat_res = supabase.table("chats").select("*").eq("id", chat_id).single().execute()
    if not chat_res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat = chat_res.data
    account = await _account_for_chat(chat, user_id)

    try:
        await sync.sync_chat_messages(account, chat)
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))

    msgs = (
        supabase.table("messages")
        .select("*")
        .eq("chat_id", chat_id)
        .order("created_at")
        .execute()
    )
    return msgs.data


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str, payload: Dict[str, Any], user_id: str = Depends(get_current_user)):
    text = (payload or {}).get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")

    chat_res = supabase.table("chats").select("*").eq("id", chat_id).single().execute()
    if not chat_res.data:
        raise HTTPException(status_code=404, detail="Chat not found")
    chat = chat_res.data
    account = await _account_for_chat(chat, user_id)

    # Optimistic row so the UI (and Realtime subscribers) see it immediately.
    pending = supabase.table("messages").insert({
        "chat_id": chat_id,
        "platform": chat["platform"],
        "external_message_id": None,
        "sender_id": account.get("external_user_id"),
        "sender_name": "Me",
        "text": text,
        "direction": "outgoing",
        "status": "sending",
    }).execute()
    message_id = pending.data[0]["id"]

    connector = _connector(chat["platform"])
    result = await connector.send_message(account, chat["external_chat_id"], text)

    if result.get("status") == "sent":
        supabase.table("messages").update({
            "status": "sent",
            "external_message_id": result.get("external_message_id"),
        }).eq("id", message_id).execute()
        supabase.table("chats").update({
            "last_message_text": text[:120],
            "last_message_at": result.get("created_at"),
        }).eq("id", chat_id).execute()
        return {"status": "sent", "message_id": message_id}

    supabase.table("messages").update({"status": "failed"}).eq("id", message_id).execute()
    raise HTTPException(status_code=502, detail=result.get("error", "Failed to send message"))
