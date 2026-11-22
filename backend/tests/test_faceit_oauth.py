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

    async def test_faceit_callback_exchanges_code_and_loads_profile(self):
        state = "test-oauth-state"
        state_cookie = main._signed_cookie(
            {"state": state, "verifier": "test-pkce-verifier", "iat": 1_900_000_000},
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
