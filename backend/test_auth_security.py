import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException
from jose import jwt

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.auth import (  # noqa: E402
    build_password_reset_fingerprint,
    create_access_token,
    create_password_reset_token,
    get_current_user,
    verify_password_reset_token,
)
from app.config import get_settings  # noqa: E402

settings = get_settings()


# ---------------------------------------------------------------------------
# Password-reset token tests (pre-existing)
# ---------------------------------------------------------------------------

class PasswordResetTokenTests(unittest.TestCase):
    def test_password_reset_token_is_bound_to_current_password_hash(self):
        token = create_password_reset_token("user-123", "hash-one")

        payload = verify_password_reset_token(token)

        self.assertEqual(payload["user_id"], "user-123")
        self.assertEqual(
            payload["password_fingerprint"],
            build_password_reset_fingerprint("hash-one"),
        )
        self.assertNotEqual(
            payload["password_fingerprint"],
            build_password_reset_fingerprint("hash-two"),
        )


# ---------------------------------------------------------------------------
# get_current_user: session-backed token enforcement tests
# ---------------------------------------------------------------------------

def _make_user(user_id: str = "user-1") -> SimpleNamespace:
    return SimpleNamespace(id=user_id, username="tester", email="t@example.com")


def _make_session(
    session_id: str = "sess-1",
    user_id: str = "user-1",
    *,
    revoked: bool = False,
    expired: bool = False,
) -> SimpleNamespace:
    if expired:
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return SimpleNamespace(
        id=session_id,
        user_id=user_id,
        revoked_at=datetime.now(timezone.utc) if revoked else None,
        expires_at=expires_at,
        last_seen_at=None,
    )


def _make_db_for_user_lookup(user, session):
    """Return a mock db that resolves user on the first execute and session on the second."""
    call_count = 0

    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    async def fake_execute(_stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _Result(user)
        return _Result(session)

    db = SimpleNamespace()
    db.execute = fake_execute
    return db


class GetCurrentUserSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_token_without_sid_raises_401(self):
        """Access tokens that carry no session id must be rejected."""
        payload = {"sub": "user-1", "type": "access"}
        db = AsyncMock()  # DB should not even be consulted for the session check.

        # We still need a user result for the first execute call.
        user = _make_user()
        db.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=user)))

        with self.assertRaises(HTTPException) as ctx:
            await get_current_user(payload=payload, db=db)

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_valid_session_backed_token_returns_user(self):
        """A token with a valid, non-revoked session id must succeed."""
        user = _make_user()
        session = _make_session()
        db = _make_db_for_user_lookup(user, session)

        payload = {"sub": "user-1", "sid": "sess-1", "type": "access"}
        result = await get_current_user(payload=payload, db=db)

        self.assertEqual(result.id, "user-1")

    async def test_revoked_session_raises_401(self):
        """A token pointing to a revoked session must be rejected."""
        user = _make_user()
        session = _make_session(revoked=True)
        db = _make_db_for_user_lookup(user, session)

        payload = {"sub": "user-1", "sid": "sess-1", "type": "access"}

        with self.assertRaises(HTTPException) as ctx:
            await get_current_user(payload=payload, db=db)

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_expired_session_raises_401(self):
        """A token pointing to an already-expired session must be rejected."""
        user = _make_user()
        session = _make_session(expired=True)
        db = _make_db_for_user_lookup(user, session)

        payload = {"sub": "user-1", "sid": "sess-1", "type": "access"}

        with self.assertRaises(HTTPException) as ctx:
            await get_current_user(payload=payload, db=db)

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_missing_session_row_raises_401(self):
        """A token with a sid that doesn't exist in the DB must be rejected."""
        user = _make_user()
        db = _make_db_for_user_lookup(user, None)  # session not found

        payload = {"sub": "user-1", "sid": "nonexistent-sess", "type": "access"}

        with self.assertRaises(HTTPException) as ctx:
            await get_current_user(payload=payload, db=db)

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_unknown_user_raises_401(self):
        """A token for a user that no longer exists must be rejected."""

        class _NoUser:
            def scalar_one_or_none(self):
                return None

        db = SimpleNamespace()
        db.execute = AsyncMock(return_value=_NoUser())

        payload = {"sub": "ghost-user", "sid": "sess-1", "type": "access"}

        with self.assertRaises(HTTPException) as ctx:
            await get_current_user(payload=payload, db=db)

        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
