from typing import Any, Dict

from .base import BaseConnector


class VKConnector(BaseConnector):
    """VK connector.

    Real VK OAuth / message access is implemented in a later phase. Until then
    this returns an honest "unavailable" status rather than a decorative stub.
    """

    platform = "vk"

    async def start_connection(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "status": "failed",
            "error": "VK connection is not available yet.",
        }
