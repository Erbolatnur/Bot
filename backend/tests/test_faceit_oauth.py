import time
import unittest
from unittest.mock import patch

import httpx

from app import main


class FakeResponse:
    is_error = False
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeOAuthClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, **kwargs):
        self.calls.append(("post", url))
        return FakeResponse({"access_token": "test-access-token"})

    async def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return FakeResponse({
            "sub": "test-faceit-user",
            "nickname": "test-player",
            "picture": "https://example.test/avatar.png",
        })


class FaceitOAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_values = {
            "session_secret": main.settings.session_secret,
            "faceit_oauth_client_id": main.settings.faceit_oauth_client_id,
            "faceit_oauth_client_secret": main.settings.faceit_oauth_client_secret,
            "faceit_oauth_redirect_url": main.settings.faceit_oauth_redirect_url,
            "frontend_origin": main.settings.frontend_origin,
        }
        main.settings.session_secret = "unit-test-session-secret"
        main.settings.faceit_oauth_client_id = "test-client-id"
        main.settings.faceit_oauth_client_secret = "test-client-secret"
        main.settings.faceit_oauth_redirect_url = "https://api.example.test/api/v1/auth/faceit/callback"
        main.settings.frontend_origin = "https://app.example.test"
        FakeOAuthClient.calls = []

    async def asyncTearDown(self):
        for key, value in self.old_values.items():
            setattr(main.settings, key, value)

    async def test_faceit_login_redirects_to_authorization_endpoint(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.get("/api/v1/auth/faceit/login", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["location"].startswith(main.FACEIT_AUTHORIZATION_ENDPOINT + "?"))
        self.assertIn(main.FACEIT_STATE_COOKIE, response.headers.get("set-cookie", ""))


    async def test_callback_rejects_unexpected_issuer(self):
        state = "test-oauth-state"
        state_cookie = main._signed_cookie(
            {"state": state, "verifier": "test-pkce-verifier", "iat": int(time.time())},
            "faceit-oauth-state",
        )
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            client.cookies.set(main.FACEIT_STATE_COOKIE, state_cookie)
            response = await client.get(
                "/api/v1/auth/faceit/callback",
                params={"code": "test-auth-code", "state": state, "iss": "https://evil.example"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("issuer", response.json()["detail"].lower())

    async def test_signed_cookie_rejects_future_timestamp(self):
        token = main._signed_cookie(
            {"state": "test", "iat": int(time.time()) + 3600},
            "faceit-oauth-state",
        )
        self.assertIsNone(main._read_signed_cookie(token, "faceit-oauth-state"))

    async def test_faceit_callback_exchanges_code_and_loads_profile(self):
        state = "test-oauth-state"
        state_cookie = main._signed_cookie(
            {"state": state, "verifier": "test-pkce-verifier", "iat": int(time.time())},
            "faceit-oauth-state",
        )
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            client.cookies.set(main.FACEIT_STATE_COOKIE, state_cookie)
            with patch.object(main.httpx, "AsyncClient", FakeOAuthClient):
                response = await client.get(
                    "/api/v1/auth/faceit/callback",
                    params={"code": "test-auth-code", "state": state},
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            FakeOAuthClient.calls,
            [
                ("post", main.FACEIT_TOKEN_ENDPOINT),
                ("get", main.FACEIT_USERINFO_ENDPOINT),
            ],
        )
        self.assertIn(main.FACEIT_COOKIE_NAME, response.headers.get("set-cookie", ""))


if __name__ == "__main__":
    unittest.main()


class SteamShareCodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_known_share_code_decodes_to_expected_identifiers(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.post(
                "/api/v1/steam/matches/decode",
                json={"share_code": "CSGO-GADqf-jjyJ8-cSP2r-smZRo-TO2xK"},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match_id"], "3230642215713767580")
        self.assertEqual(data["reservation_id"], "3230647599455273103")
        self.assertEqual(data["tv_port"], 55788)
        self.assertFalse(data["metadata_available"])
        self.assertIn("csgo_download_match", data["steam_launch_uri"])

    async def test_invalid_share_code_is_rejected(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.post(
                "/api/v1/steam/matches/decode",
                json={"share_code": "not-a-valid-share-code"},
            )

        self.assertEqual(response.status_code, 422)


class DemoUploadAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_upload_requires_login(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.post(
                "/api/v1/demos",
                files={"file": ("match.dem", b"PBDEMS2-invalid", "application/octet-stream")},
            )
        self.assertEqual(response.status_code, 401)

    async def test_demo_list_requires_login(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.get("/api/v1/demos")
        self.assertEqual(response.status_code, 401)


class DemoCorsTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_preflight_is_allowed(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.options(
                "/api/v1/demos/test-id",
                headers={
                    "Origin": main.settings.frontend_origin,
                    "Access-Control-Request-Method": "DELETE",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("DELETE", response.headers.get("access-control-allow-methods", ""))
