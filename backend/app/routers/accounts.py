from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict

from ..database import supabase
from ..dependencies import get_current_user
from ..services.account_connection import connection_service

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

ALLOWED_PLATFORMS = {"instagram", "max", "vk"}


@router.get("")
async def get_accounts(user_id: str = Depends(get_current_user)):
    """List the user's accounts WITHOUT any stored secrets."""
    res = (
        supabase.table("accounts")
        .select("id, platform, username, display_name, avatar_url, status, created_at")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return res.data


@router.post("/{platform}/connect")
async def connect_account(platform: str, payload: Dict[str, Any] | None = None, user_id: str = Depends(get_current_user)):
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Invalid platform")
    return await connection_service.start_connection(user_id, platform, payload)


@router.post("/connections/{connection_id}/verify")
async def verify_connection(connection_id: str, payload: Dict[str, Any], user_id: str = Depends(get_current_user)):
    """Submit a 2FA or challenge code for a pending connection."""
    code = (payload or {}).get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Code is required")
    return await connection_service.submit_code(connection_id, code)


@router.get("/connections/{connection_id}")
async def get_connection_status(connection_id: str, user_id: str = Depends(get_current_user)):
    return await connection_service.get_status(connection_id)


@router.post("/connections/{connection_id}/cancel")
async def cancel_connection(connection_id: str, user_id: str = Depends(get_current_user)):
    return await connection_service.cancel_connection(connection_id)


@router.delete("/{account_id}")
async def delete_account(account_id: str, user_id: str = Depends(get_current_user)):
    account = (
        supabase.table("accounts")
        .select("id, platform, session_data_encrypted")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not account.data:
        raise HTTPException(status_code=404, detail="Account not found")

    # Best-effort remote disconnect.
    from ..connectors.instagram import InstagramConnector
    from ..connectors.max import MaxConnector
    from ..connectors.vk import VKConnector

    connectors = {
        "instagram": InstagramConnector,
        "max": MaxConnector,
        "vk": VKConnector,
    }
    try:
        connector = connectors[account.data["platform"]]()
        await connector.disconnect(account.data)
    except Exception:  # noqa: BLE001 - disconnection is best-effort
        pass

    supabase.table("accounts").delete().eq("id", account_id).execute()
    supabase.table("chats").delete().eq("account_id", account_id).execute()
    return {"status": "deleted"}
