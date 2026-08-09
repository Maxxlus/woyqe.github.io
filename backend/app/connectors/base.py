"""Base class for messenger connectors.

Design notes
------------
Every method has a working default so a connector can be instantiated even
when it only implements part of the flow (this is what previously crashed the
whole app: abstract methods with no body). A connector overrides exactly the
capabilities it supports.

The connection lifecycle is expressed through the ``status`` field returned by
``start_connection`` / ``submit_code`` / ``get_connection_status``:

    connecting            - work in progress (transient)
    connected             - session established AND verifiable
    2fa_required          - user must submit a 2FA code
    challenge_required    - user must submit a challenge code (email/sms)
    waiting_for_scan      - a real QR was issued, waiting for the user to scan
    waiting_for_confirmation - OAuth/device flow started, waiting for approval
    failed                - terminal error (``error`` describes it)
    timeout               - the pending flow expired
"""

from typing import Any, Dict, List


class ConnectorError(Exception):
    """Raised for connector-level failures that should surface to the API."""


class BaseConnector:
    platform: str = "base"

    # ---- connection lifecycle -------------------------------------------------

    async def start_connection(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Begin connecting an account (login / QR / OAuth)."""
        return {"status": "failed", "error": f"{self.platform}: not implemented"}

    async def submit_code(self, connection_id: str, code: str) -> Dict[str, Any]:
        """Submit a 2FA / challenge / confirmation code for a pending connection."""
        return {"status": "failed", "error": f"{self.platform}: code submission not supported"}

    async def get_connection_status(self, connection_id: str) -> Dict[str, Any]:
        """Poll a pending connection (e.g. whether a QR has been scanned)."""
        return {"status": "failed", "error": f"{self.platform}: status polling not supported"}

    async def cancel_connection(self, connection_id: str) -> Dict[str, Any]:
        """Abort a pending connection and free any in-memory state."""
        return {"status": "cancelled"}

    async def disconnect(self, account_data: Dict[str, Any]) -> None:
        """Tear down a live account session (best-effort)."""
        return None

    # ---- data access (require a stored account) -------------------------------

    async def get_profile(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the real profile of the connected account.

        Used to *prove* a connection is live before we mark it connected.
        Must raise ConnectorError (or return {}) if the session is invalid.
        """
        raise ConnectorError(f"{self.platform}: get_profile not implemented")

    async def get_chats(self, account_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []

    async def get_messages(self, account_data: Dict[str, Any], external_chat_id: str) -> List[Dict[str, Any]]:
        return []

    async def send_message(self, account_data: Dict[str, Any], external_chat_id: str, text: str) -> Dict[str, Any]:
        return {"status": "failed", "error": f"{self.platform}: send not implemented"}
