import unittest
from unittest.mock import patch

import httpx

from app import main


class ProjectApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_secret = main.settings.session_secret
        self.old_storage_ready = main.storage_ready
        main.settings.session_secret = "project-api-test-secret"
        main.storage_ready = True

    async def asyncTearDown(self):
        main.settings.session_secret = self.old_secret
        main.storage_ready = self.old_storage_ready

    async def test_projects_require_authentication(self):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            response = await client.get("/api/v1/projects")
        self.assertEqual(response.status_code, 401)

    async def test_project_create_is_scoped_to_signed_steam_identity(self):
        cookie = main._make_session("76561198000000000")
        expected = {
            "id": "project-test-id",
            "title": "My match",
            "description": "",
            "status": "created",
            "data": {},
        }
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            client.cookies.set(main.COOKIE_NAME, cookie)
            with patch.object(main.storage, "create_project", return_value=expected) as create:
                response = await client.post("/api/v1/projects", json={"title": "My match"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["item"]["id"], "project-test-id")
        create.assert_called_once_with("steam", "76561198000000000", "My match", "", {})

    async def test_project_list_does_not_mix_provider_accounts(self):
        cookie = main._make_session("76561198000000000")
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            client.cookies.set(main.COOKIE_NAME, cookie)
            with patch.object(main.storage, "list_projects", return_value=[]) as list_items:
                response = await client.get("/api/v1/projects")
        self.assertEqual(response.status_code, 200)
        list_items.assert_called_once_with("steam", "76561198000000000")


if __name__ == "__main__":
    unittest.main()
