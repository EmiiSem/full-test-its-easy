import re
from typing import Any

import httpx


class KeitaroError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def api_root(base_url: str) -> str:
    root = base_url.strip().rstrip("/")
    root = re.sub(r"/admin$", "", root)
    if root.endswith("/admin_api/v1"):
        return root
    return root + "/admin_api/v1"


class KeitaroClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        if not api_key.strip():
            raise KeitaroError(500, "В backend/.env не задан KEITARO_API_KEY")
        self.client = httpx.Client(
            base_url=api_root(base_url),
            headers={
                "Api-Key": api_key.strip(),
                "Accept": "application/json",
                "User-Agent": "keitaro-wrapper",
            },
            timeout=40,
        )

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        response = self.client.request(method, path, json=payload)
        if response.status_code >= 400:
            raise KeitaroError(response.status_code, _error_message(response))
        if not response.content:
            return None
        return response.json()

    def list_domains(self) -> list[dict[str, Any]]:
        return self.request("GET", "/domains")

    def list_groups(self) -> list[dict[str, Any]]:
        return self.request("GET", "/groups?type=campaigns")

    def list_sources(self) -> list[dict[str, Any]]:
        return self.request("GET", "/traffic_sources")

    def list_offers(self) -> list[dict[str, Any]]:
        return self.request("GET", "/offers")

    def list_campaigns(self) -> list[dict[str, Any]]:
        return self.request("GET", "/campaigns")

    def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        return self.request("GET", f"/campaigns/{campaign_id}")

    def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/campaigns", payload)

    def delete_campaign(self, campaign_id: int) -> Any:
        return self.request("DELETE", f"/campaigns/{campaign_id}")

    def list_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        return self.request("GET", f"/campaigns/{campaign_id}/streams")

    def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/streams", payload)

    def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/streams/{stream_id}", payload)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"Keitaro ответил {response.status_code}"
    if isinstance(body, dict):
        for key in ("error", "message", "detail"):
            value = body.get(key)
            if value:
                return str(value)
        return str(body)
    if isinstance(body, str) and body.strip():
        return body.strip()
    return f"Keitaro ответил {response.status_code}"
