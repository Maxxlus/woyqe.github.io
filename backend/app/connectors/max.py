from typing import Any, Dict

from .base import BaseConnector


class MaxConnector(BaseConnector):
    """MAX messenger connector.

    Real QR-based user authentication is implemented in a later phase. Until
    then this returns an honest "unavailable" status rather than a fake QR.
    """

    platform = "max"

    async def start_connection(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "status": "failed",
            "error": "MAX connection is not available yet.",
        }
