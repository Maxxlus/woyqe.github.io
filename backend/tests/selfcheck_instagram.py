"""Offline self-check for the Instagram connector's logic.

This does NOT hit Instagram or Supabase. It drives the connector through a
stub client that mimics instagrapi's real return types, to verify our
login/2FA flow, session round-trip and data mapping are correct.

Run:  .venv/Scripts/python.exe -m tests.selfcheck_instagram
Exits non-zero on the first failed assertion.
"""

import asyncio
import json
from datetime import datetime, timezone

from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

from app.connectors.instagram import InstagramConnector, PENDING
from app.core.security import encryptor


# ---- stub instagrapi model objects ---------------------------------------

class FakeUser:
    def __init__(self, pk, username, full_name, pic):
        self.pk = pk
        self.username = username
        self.full_name = full_name
        self.profile_pic_url = pic


class FakeMsg:
    def __init__(self, id, user_id, text, ts, is_sent_by_viewer):
        self.id = id
        self.user_id = user_id
        self.text = text
        self.timestamp = ts
        self.is_sent_by_viewer = is_sent_by_viewer


class FakeThread:
    def __init__(self, id, users, messages, is_group=False, thread_title="", seen=True):
        self.id = id
        self.users = users
        self.messages = messages
        self.is_group = is_group
        self.thread_title = thread_title
        self._seen = seen

    def is_seen(self, my_id):
        return self._seen


class FakeAccount:
    def __init__(self, pk, username, full_name, pic):
        self.pk = pk
        self.username = username
        self.full_name = full_name
        self.profile_pic_url = pic


class FakeDM:
    def __init__(self, id, ts):
        self.id = id
        self.timestamp = ts


class FakeClient:
    def __init__(self, needs_2fa=False):
        self.user_id = 555
        self.username = "me_user"
        self.needs_2fa = needs_2fa
        self.sent = []
        self.challenge_code_handler = None

    def login(self, username=None, password=None, relogin=False, verification_code=""):
        if self.needs_2fa and not verification_code:
            raise TwoFactorRequired("2FA needed")
        return True

    def account_info(self):
        return FakeAccount("555", "me_user", "Me Real", "http://img/me.jpg")

    def get_settings(self):
        return {"uuids": {"uuid": "x"}, "authorization_data": {"token": "t"}, "last_login": 1.0}

    def set_settings(self, s):
        self._settings = s
        return True

    def direct_threads(self, amount=20):
        me = FakeUser("555", "me_user", "Me Real", "http://img/me.jpg")
        alice = FakeUser("111", "alice", "Alice Wonderland", "http://img/alice.jpg")
        msgs = [
            FakeMsg("m2", "111", "hey there", datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc), False),
            FakeMsg("m1", "555", "hi", datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc), True),
        ]
        return [FakeThread("340", [me, alice], msgs, seen=False)]

    def direct_thread(self, tid, amount=30):
        me = FakeUser("555", "me_user", "Me Real", None)
        alice = FakeUser("111", "alice", "Alice Wonderland", None)
        msgs = [
            FakeMsg("m2", "111", "hey there", datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc), False),
            FakeMsg("m1", "555", "hi", datetime(2026, 8, 9, 9, 0, tzinfo=timezone.utc), True),
        ]
        return FakeThread(str(tid), [me, alice], msgs)

    def direct_send(self, text, user_ids=None, thread_ids=None):
        self.sent.append((text, thread_ids))
        return FakeDM("newmsg99", datetime(2026, 8, 9, 11, 0, tzinfo=timezone.utc))


def check(name, cond):
    if not cond:
        raise AssertionError(f"FAILED: {name}")
    print(f"  ok  {name}")


async def main():
    print("Instagram connector self-check")

    # 1) session round-trip through the REAL encryptor + a REAL Client (offline).
    real = Client()
    real.set_settings(FakeClient().get_settings())
    real.authorization_data = {"token": "t"}
    enc = encryptor.encrypt(json.dumps(real.get_settings()))
    account = {"session_data_encrypted": enc}
    conn = InstagramConnector()
    rebuilt = conn._get_client(account)
    check("session decrypts & loads", rebuilt.get_settings()["authorization_data"] == {"token": "t"})

    # 2) immediate login success → connected payload with encrypted session.
    conn._new_client = lambda: FakeClient(needs_2fa=False)
    res = await conn.start_connection({"username": "me_user", "password": "pw"})
    check("login connected", res["status"] == "connected")
    check("external_user_id set", res["external_user_id"] == "555")
    check("no password persisted", "password" not in res and "pw" not in json.dumps(res))
    check("session is encrypted (not plaintext json)", "authorization_data" not in res["session_data_encrypted"])

    # 3) 2FA path → pending, then submit_code → connected.
    fake2fa = FakeClient(needs_2fa=True)
    conn._new_client = lambda: fake2fa
    res2 = await conn.start_connection({"username": "u", "password": "p"})
    check("2fa_required returned", res2["status"] == "2fa_required")
    cid = res2["connection_id"]
    check("pending stored", cid in PENDING)
    done = await conn.submit_code(cid, "123456")
    check("2fa submit connected", done["status"] == "connected")
    check("pending cleared", cid not in PENDING)

    # 4) get_profile mapping.
    conn._get_client = lambda account_data: FakeClient()
    prof = await conn.get_profile(account)
    check("profile username", prof["username"] == "me_user")
    check("profile display_name", prof["display_name"] == "Me Real")
    check("profile avatar", prof["avatar_url"] == "http://img/me.jpg")

    # 5) get_chats mapping: title from the other user, unread counts incoming only.
    chats = await conn.get_chats(account)
    check("one chat", len(chats) == 1)
    c = chats[0]
    check("chat title = other user's name", c["title"] == "Alice Wonderland")
    check("chat external id", c["external_chat_id"] == "340")
    check("last message text", c["last_message_text"] == "hey there")
    check("unread counts only incoming (=1)", c["unread_count"] == 1)
    check("avatar from other user", c["avatar_url"] == "http://img/alice.jpg")

    # 6) get_messages mapping: direction + chronological order.
    msgs = await conn.get_messages(account, "340")
    check("two messages", len(msgs) == 2)
    check("oldest first", msgs[0]["external_message_id"] == "m1")
    check("my message outgoing", msgs[0]["direction"] == "outgoing")
    check("their message incoming", msgs[1]["direction"] == "incoming")
    check("their sender name resolved", msgs[1]["sender_name"] == "Alice Wonderland")

    # 7) send_message: correct thread_ids (list of int) + returns real id.
    fc = FakeClient()
    conn._get_client = lambda account_data: fc
    sent = await conn.send_message(account, "340", "hello world")
    check("send status sent", sent["status"] == "sent")
    check("send returns real id", sent["external_message_id"] == "newmsg99")
    check("direct_send got thread_ids=[340] as int", fc.sent == [("hello world", [340])])

    print("\nALL INSTAGRAM CONNECTOR CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
