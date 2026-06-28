from __future__ import annotations

import httpx


class CkanClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    async def datastore_search(
        self, resource_id: str, q: str | None = None, limit: int = 25
    ) -> list[dict]:
        params: dict[str, object] = {"resource_id": resource_id, "limit": limit}
        if q:
            params["q"] = q
        url = f"{self.base_url}/api/3/action/datastore_search"

        async def _do(client: httpx.AsyncClient) -> list[dict]:
            resp = await client.get(url, params=params, timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                return []
            return payload["result"]["records"]

        if self._client is not None:
            return await _do(self._client)
        async with httpx.AsyncClient() as client:
            return await _do(client)
