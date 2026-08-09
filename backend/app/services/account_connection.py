"""Orchestrates the account connection lifecycle for all platforms.

After a connector signals 'connected', this service *proves* the connection is
real by fetching the profile. Only then do we persist the account.
"""

import logging
from typing import Any, Dict

from ..connectors.base import BaseConnector, ConnectorError
from ..connectors.instagram import InstagramConnector
from ..connectors.max import MaxConnector
from ..connectors.vk import VKConnector
from ..database import supabase

logger = logging.getLogger(__name__)


class AccountConnectionService:
    def __init__(self):
        self.connectors: Dict[str, type[BaseConnector]] = {
            "instagram": InstagramConnector,
            "max": MaxConnector,
            "vk": VKConnector,
        }

    async def start_connection(
        self, user_id: str, platform: str, payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        if platform not in self.connectors:
            return {"status": "failed", "error": f"Unknown platform: {platform}"}

        connector = self.connectors[platform]()
        result = await connector.start_connection(payload)

        # Immediate success: verify the session and save the account.
        if result.get("status") == "connected":
            return await self._finalize_connection(user_id, platform, result, connector)

        # Intermediate states (2fa / challenge / waiting_for_scan / etc.):
        # save a pending record so we can retrieve it later on submit_code/poll.
        if result.get("status") in ("2fa_required", "challenge_required", "waiting_for_scan", "waiting_for_confirmation"):
            connection_id = result.get("connection_id")
            if connection_id:
                supabase.table("account_connections").insert({
                    "id": connection_id,
                    "user_id": user_id,
                    "platform": platform,
                    "method": result.get("method", "unknown"),
                    "status": result["status"],
                }).execute()
            return result

        # Terminal failure.
        return result

    async def submit_code(self, connection_id: str, code: str) -> Dict[str, Any]:
        conn_res = (
            supabase.table("account_connections")
            .select("*")
            .eq("id", connection_id)
            .single()
            .execute()
        )
        if not conn_res.data:
            return {"status": "failed", "error": "Connection not found or expired"}

        platform = conn_res.data["platform"]
        user_id = conn_res.data["user_id"]
        connector = self.connectors[platform]()
        result = await connector.submit_code(connection_id, code)

        if result.get("status") == "connected":
            # Delete the pending connection record.
            supabase.table("account_connections").delete().eq("id", connection_id).execute()
            return await self._finalize_connection(user_id, platform, result, connector)

        return result

    async def get_status(self, connection_id: str) -> Dict[str, Any]:
        res = (
            supabase.table("account_connections")
            .select("*")
            .eq("id", connection_id)
            .single()
            .execute()
        )
        if not res.data:
            return {"status": "failed", "error": "Connection not found"}
        return {
            "connection_id": connection_id,
            "platform": res.data["platform"],
            "method": res.data.get("method", "unknown"),
            "status": res.data["status"],
        }

    async def cancel_connection(self, connection_id: str) -> Dict[str, Any]:
        res = (
            supabase.table("account_connections")
            .select("platform")
            .eq("id", connection_id)
            .single()
            .execute()
        )
        if res.data:
            platform = res.data["platform"]
            connector = self.connectors[platform]()
            await connector.cancel_connection(connection_id)
        supabase.table("account_connections").delete().eq("id", connection_id).execute()
        return {"status": "cancelled"}

    # ---- finalization (verify + persist) --------------------------------------

    async def _finalize_connection(
        self, user_id: str, platform: str, conn_result: Dict[str, Any], connector: BaseConnector
    ) -> Dict[str, Any]:
        """Prove the session is real by fetching the profile, then save the account."""
        session_encrypted = conn_result.get("session_data_encrypted")
        if not session_encrypted:
            logger.error("[%s] Connected but no encrypted session returned", platform.upper())
            return {"status": "failed", "error": "Internal error: no session data"}

        temp_account = {"session_data_encrypted": session_encrypted}
        try:
            profile = await connector.get_profile(temp_account)
        except ConnectorError as e:
            logger.error("[%s] Connected but profile fetch failed: %s", platform.upper(), e)
            return {"status": "failed", "error": f"Could not verify account: {e}"}

        # Merge any profile fields from the connector into what we store.
        external_user_id = profile.get("external_user_id") or conn_result.get("external_user_id")
        username = profile.get("username") or conn_result.get("username")
        display_name = profile.get("display_name") or username
        avatar_url = profile.get("avatar_url")

        # Check for an existing account (re-auth).
        existing = (
            supabase.table("accounts")
            .select("id")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .execute()
        )
        if existing.data:
            account_id = existing.data[0]["id"]
            supabase.table("accounts").update({
                "username": username,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "external_user_id": external_user_id,
                "status": "connected",
                "session_data_encrypted": session_encrypted,
            }).eq("id", account_id).execute()
            return {"status": "connected", "account_id": account_id, "platform": platform}

        # New account.
        new_acc = supabase.table("accounts").insert({
            "user_id": user_id,
            "platform": platform,
            "username": username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "external_user_id": external_user_id,
            "status": "connected",
            "session_data_encrypted": session_encrypted,
        }).execute()
        return {
            "status": "connected",
            "account_id": new_acc.data[0]["id"],
            "platform": platform,
        }


connection_service = AccountConnectionService()
