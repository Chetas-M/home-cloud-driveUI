import os
import unittest

from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.routers import auth as auth_router  # noqa: E402


def make_request(host: str, *, headers: dict[str, str] | None = None, client_host: str = "203.0.113.10") -> Request:
    encoded_headers = [(b"host", host.encode("ascii"))]
    for key, value in (headers or {}).items():
        encoded_headers.append((key.lower().encode("ascii"), value.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/auth/forgot-password",
            "headers": encoded_headers,
            "server": (host, 443),
            "client": (client_host, 12345),
        }
    )


class PasswordResetUrlTests(unittest.TestCase):
    def setUp(self):
        self.original_password_reset_url = auth_router.settings.password_reset_url
        self.original_cors_origins_str = auth_router.settings.cors_origins_str
        self.original_trust_proxy_headers = auth_router.settings.trust_proxy_headers

    def tearDown(self):
        auth_router.settings.password_reset_url = self.original_password_reset_url
        auth_router.settings.cors_origins_str = self.original_cors_origins_str
        auth_router.settings.trust_proxy_headers = self.original_trust_proxy_headers

    def test_uses_configured_reset_url_when_present(self):
        auth_router.settings.password_reset_url = "https://app.example.com/reset-password?source=email"
        auth_router.settings.cors_origins_str = "https://app.example.com"

        url = auth_router.build_password_reset_url(make_request("evil.example"), "token123")

        self.assertEqual(
            url,
            "https://app.example.com/reset-password?source=email&reset_token=token123",
        )

    def test_falls_back_to_configured_origin_when_request_host_is_untrusted(self):
        auth_router.settings.password_reset_url = None
        auth_router.settings.cors_origins_str = "https://app.example.com,https://admin.example.com"

        url = auth_router.build_password_reset_url(make_request("evil.example"), "token123")

        self.assertEqual(url, "https://app.example.com/?reset_token=token123")

    def test_client_ip_ignores_proxy_headers_by_default(self):
        auth_router.settings.trust_proxy_headers = False
        request = make_request(
            "app.example.com",
            headers={
                "x-forwarded-for": "198.51.100.20, 192.0.2.5",
                "x-real-ip": "198.51.100.21",
            },
            client_host="203.0.113.44",
        )

        client_ip = auth_router.get_client_ip(request)

        self.assertEqual(client_ip, "203.0.113.44")

    def test_client_ip_can_use_proxy_headers_when_explicitly_enabled(self):
        auth_router.settings.trust_proxy_headers = True
        request = make_request(
            "app.example.com",
            headers={"x-forwarded-for": "198.51.100.20, 192.0.2.5"},
            client_host="203.0.113.44",
        )

        client_ip = auth_router.get_client_ip(request)

        self.assertEqual(client_ip, "198.51.100.20")

    def test_client_ip_ignores_invalid_forwarded_header_and_falls_back(self):
        auth_router.settings.trust_proxy_headers = True
        request = make_request(
            "app.example.com",
            headers={
                "x-forwarded-for": "not-an-ip",
                "x-real-ip": "198.51.100.21",
            },
            client_host="203.0.113.44",
        )

        client_ip = auth_router.get_client_ip(request)

        self.assertEqual(client_ip, "198.51.100.21")


if __name__ == "__main__":
    unittest.main()
