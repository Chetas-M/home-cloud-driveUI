import unittest

from app.config import Settings


class PasswordResetConfigTests(unittest.TestCase):
    def test_password_reset_disabled_without_resend_api_key(self):
        settings = Settings(
            secret_key="0123456789abcdef0123456789abcdef",
            resend_from_email="no-reply@example.com",
        )

        self.assertFalse(settings.password_reset_enabled)
        self.assertEqual(settings.email_delivery_config_error, "Resend API key is missing")

    def test_password_reset_disabled_without_resend_sender_email(self):
        settings = Settings(
            secret_key="0123456789abcdef0123456789abcdef",
            resend_api_key="re_test_123",
        )

        self.assertFalse(settings.password_reset_enabled)
        self.assertEqual(settings.email_delivery_config_error, "Resend sender email is missing")

    def test_password_reset_enabled_with_valid_resend_configuration(self):
        settings = Settings(
            secret_key="0123456789abcdef0123456789abcdef",
            resend_api_key="re_test_123",
            resend_from_email="no-reply@example.com",
        )

        self.assertTrue(settings.email_delivery_enabled)
        self.assertTrue(settings.password_reset_enabled)
        self.assertIsNone(settings.email_delivery_config_error)


if __name__ == "__main__":
    unittest.main()
