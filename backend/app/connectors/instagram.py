import asyncio
import json
import logging
import queue
import threading
import time
import uuid
from typing import Any, Dict, List

from instagrapi import Client
from instagrapi.exceptions import (
    BadCredentials,
    BadPassword,
    ChallengeRequired,
    ClientError,
    LoginRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
    TwoFactorRequired,
)

from .base import BaseConnector, ConnectorError
from ..core.security import encryptor

logger = logging.getLogger(__name__)

# In-memory store of half-finished logins (client objects can't be serialised).
# Keyed by connection_id. Single-process only — fine for this MVP.
PENDING: Dict[str, "PendingLogin"] = {}

CODE_WAIT_SECONDS = 300
PENDING_TTL_SECONDS = 600


class PendingLogin:
    def __init__(self, cl: Client, username: str, password: str, kind: str):
        self.cl = cl
        self.username = username
        self.password = password
        self.kind = kind  # "2fa" | "challenge"
        self.created_at = time.time()
        self.code_queue: "queue.Queue[str]" = queue.Queue(maxsize=1)
        self.finished = threading.Event()
        self.result: Dict[str, Any] = {}
        self.thread: threading.Thread | None = None

    def expired(self) -> bool:
        return (time.time() - self.created_at) > PENDING_TTL_SECONDS


def _purge_expired() -> None:
    for cid in [c for c, p in PENDING.items() if p.expired()]:
        PENDING.pop(cid, None)


def _session_payload(cl: Client, username: str) -> Dict[str, Any]:
    """Everything we persist after a successful login (no password!)."""
    return {
        "method": "credentials",
        "status": "connected",
        "session_data_encrypted": encryptor.encrypt(json.dumps(cl.get_settings())),
        "external_user_id": str(cl.user_id),
        "username": username or cl.username,
    }


class InstagramConnector(BaseConnector):
    platform = "instagram"

    # ---- client construction --------------------------------------------------

    def _new_client(self) -> Client:
        cl = Client()
        cl.delay_range = [1, 3]
        return cl

    def _get_client(self, account_data: Dict[str, Any]) -> Client:
        """Rebuild an authenticated client from the stored encrypted session."""
        cl = self._new_client()
        enc = account_data.get("session_data_encrypted")
        if not enc:
            raise ConnectorError("No stored session for this account")
        try:
            settings_dict = json.loads(encryptor.decrypt(enc))
            cl.set_settings(settings_dict)
        except Exception as e:
            logger.error("[INSTAGRAM] Failed to load session: %s", e)
            raise ConnectorError("Stored session is corrupt or unreadable")
        return cl

    # ---- connection lifecycle -------------------------------------------------

    async def start_connection(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        _purge_expired()
        payload = payload or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not username or not password:
            return {"status": "failed", "error": "Username and password required"}

        cl = self._new_client()

        def _login():
            cl.login(username, password)

        try:
            await asyncio.to_thread(_login)
            # Prove the session is real before declaring success.
            await asyncio.to_thread(cl.account_info)
            return _session_payload(cl, username)
        except TwoFactorRequired:
            conn_id = str(uuid.uuid4())
            PENDING[conn_id] = PendingLogin(cl, username, password, "2fa")
            return {"status": "2fa_required", "connection_id": conn_id}
        except ChallengeRequired:
            conn_id = str(uuid.uuid4())
            pending = PendingLogin(cl, username, password, "challenge")
            PENDING[conn_id] = pending
            self._start_challenge_resolver(pending)
            return {"status": "challenge_required", "connection_id": conn_id}
        except (BadPassword, BadCredentials):
            return {"status": "failed", "error": "Incorrect username or password"}
        except (PleaseWaitFewMinutes, RateLimitError):
            return {"status": "failed", "error": "Instagram rate-limited this login. Try again later."}
        except ClientError as e:
            logger.error("[INSTAGRAM] Login ClientError: %s", e)
            return {"status": "failed", "error": str(e) or "Instagram login failed"}
        except Exception as e:  # noqa: BLE001 - surface the real reason
            logger.exception("[INSTAGRAM] Unexpected login error")
            return {"status": "failed", "error": str(e) or "Unexpected error"}

    def _start_challenge_resolver(self, pending: PendingLogin) -> None:
        """Resolve the checkpoint in a background thread.

        instagrapi's challenge flow is blocking: it selects a verification
        method (which makes Instagram send the code) and then calls
        challenge_code_handler to read the code. We feed that handler from a
        queue that submit_code() fills once the user types the code in.
        """
        cl = pending.cl

        def _handler(_username: str, _choice) -> str:
            return pending.code_queue.get(timeout=CODE_WAIT_SECONDS)

        cl.challenge_code_handler = _handler

        def _resolve():
            try:
                cl.challenge_resolve(cl.last_json)
                cl.login(pending.username, pending.password)
                cl.account_info()
                pending.result = {"ok": True}
            except Exception as e:  # noqa: BLE001
                logger.error("[INSTAGRAM] Challenge resolve failed: %s", e)
                pending.result = {"ok": False, "error": str(e) or "Challenge failed"}
            finally:
                pending.finished.set()

        pending.thread = threading.Thread(target=_resolve, daemon=True)
        pending.thread.start()

    async def submit_code(self, connection_id: str, code: str) -> Dict[str, Any]:
        pending = PENDING.get(connection_id)
        if not pending:
            return {"status": "failed", "error": "Connection expired. Start again."}
        code = (code or "").strip()
        if not code:
            return {"status": "failed", "error": "Code is required"}

        try:
            if pending.kind == "2fa":
                cl = pending.cl

                def _verify():
                    cl.login(pending.username, pending.password, verification_code=code)

                await asyncio.to_thread(_verify)
                await asyncio.to_thread(cl.account_info)
                PENDING.pop(connection_id, None)
                return _session_payload(cl, pending.username)

            # challenge: hand the code to the waiting resolver thread
            pending.code_queue.put(code)
            await asyncio.to_thread(pending.finished.wait, CODE_WAIT_SECONDS)
            if not pending.finished.is_set():
                return {"status": "failed", "error": "Timed out waiting for Instagram"}
            if pending.result.get("ok"):
                cl = pending.cl
                PENDING.pop(connection_id, None)
                return _session_payload(cl, pending.username)
            PENDING.pop(connection_id, None)
            return {"status": "failed", "error": pending.result.get("error", "Verification failed")}

        except TwoFactorRequired:
            return {"status": "failed", "error": "Invalid 2FA code"}
        except (BadPassword, BadCredentials):
            return {"status": "failed", "error": "Invalid code"}
        except Exception as e:  # noqa: BLE001
            logger.exception("[INSTAGRAM] submit_code error")
            return {"status": "failed", "error": str(e) or "Verification failed"}

    async def cancel_connection(self, connection_id: str) -> Dict[str, Any]:
        PENDING.pop(connection_id, None)
        return {"status": "cancelled"}

    # ---- data access ----------------------------------------------------------

    async def get_profile(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        cl = self._get_client(account_data)

        def _sync():
            info = cl.account_info()
            return {
                "external_user_id": str(info.pk),
                "username": info.username,
                "display_name": info.full_name or info.username,
                "avatar_url": str(info.profile_pic_url) if info.profile_pic_url else None,
            }

        try:
            return await asyncio.to_thread(_sync)
        except LoginRequired:
            raise ConnectorError("Instagram session expired — reconnect the account")
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"Failed to fetch profile: {e}")

    async def get_chats(self, account_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        cl = self._get_client(account_data)

        def _sync():
            my_id = str(cl.user_id)
            threads = cl.direct_threads(amount=20)
            chats: List[Dict[str, Any]] = []
            for t in threads:
                others = [u for u in t.users if str(u.pk) != my_id] or list(t.users)
                if t.is_group and t.thread_title:
                    title = t.thread_title
                elif others:
                    title = others[0].full_name or others[0].username
                else:
                    title = t.thread_title or "Instagram chat"
                avatar = None
                if others and others[0].profile_pic_url:
                    avatar = str(others[0].profile_pic_url)
                last = t.messages[0] if t.messages else None
                try:
                    seen = t.is_seen(my_id)
                except Exception:
                    seen = True
                unread = 0 if seen else sum(1 for m in t.messages if not m.is_sent_by_viewer)
                chats.append({
                    "external_chat_id": str(t.id),
                    "title": title,
                    "avatar_url": avatar,
                    "last_message_text": (last.text or "")[:120] if last else "",
                    "last_message_at": last.timestamp.isoformat() if last and last.timestamp else None,
                    "unread_count": unread,
                })
            return chats

        try:
            return await asyncio.to_thread(_sync)
        except LoginRequired:
            raise ConnectorError("Instagram session expired — reconnect the account")
        except Exception as e:  # noqa: BLE001
            logger.error("[INSTAGRAM] get_chats error: %s", e)
            raise ConnectorError(f"Failed to fetch chats: {e}")

    async def get_messages(self, account_data: Dict[str, Any], external_chat_id: str) -> List[Dict[str, Any]]:
        cl = self._get_client(account_data)

        def _sync():
            my_id = str(cl.user_id)
            thread = cl.direct_thread(int(external_chat_id), amount=30)
            names = {str(u.pk): (u.full_name or u.username) for u in thread.users}
            out: List[Dict[str, Any]] = []
            for m in reversed(thread.messages):
                outgoing = bool(m.is_sent_by_viewer) or str(m.user_id) == my_id
                out.append({
                    "external_message_id": str(m.id),
                    "sender_id": str(m.user_id) if m.user_id else my_id,
                    "sender_name": "Me" if outgoing else names.get(str(m.user_id), "Them"),
                    "text": m.text or "",
                    "direction": "outgoing" if outgoing else "incoming",
                    "created_at": m.timestamp.isoformat() if m.timestamp else None,
                })
            return out

        try:
            return await asyncio.to_thread(_sync)
        except LoginRequired:
            raise ConnectorError("Instagram session expired — reconnect the account")
        except Exception as e:  # noqa: BLE001
            logger.error("[INSTAGRAM] get_messages error: %s", e)
            raise ConnectorError(f"Failed to fetch messages: {e}")

    async def send_message(self, account_data: Dict[str, Any], external_chat_id: str, text: str) -> Dict[str, Any]:
        cl = self._get_client(account_data)

        def _sync():
            dm = cl.direct_send(text, thread_ids=[int(external_chat_id)])
            return {
                "status": "sent",
                "external_message_id": str(dm.id),
                "created_at": dm.timestamp.isoformat() if getattr(dm, "timestamp", None) else None,
            }

        try:
            return await asyncio.to_thread(_sync)
        except Exception as e:  # noqa: BLE001
            logger.error("[INSTAGRAM] send_message error: %s", e)
            return {"status": "failed", "error": str(e)}
