import os
import unittest

from pydantic import ValidationError

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.schemas import AdminUserUpdate  # noqa: E402


class AdminUserUpdateValidationTests(unittest.TestCase):
    def test_rejects_negative_storage_quota(self):
        with self.assertRaises(ValidationError):
            AdminUserUpdate(storage_quota=-1)

    def test_rejects_too_short_username(self):
        with self.assertRaises(ValidationError):
            AdminUserUpdate(username="ab")

    def test_accepts_valid_partial_update(self):
        update = AdminUserUpdate(storage_quota=1024, username="alice-admin")

        self.assertEqual(update.storage_quota, 1024)
        self.assertEqual(update.username, "alice-admin")


if __name__ == "__main__":
    unittest.main()
