"""Shared HTTP plumbing for Gigalogy services (DRY: keys, headers and errors live here once)."""

import requests

from ..errors import ServiceUnavailableError


class GigalogyClient:
    service_name = "Gigalogy"

    def __init__(self, base_url: str, project_key: str, api_key: str,
                 http: requests.Session | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {"project-key": project_key, "api-key": api_key}
        self._http = http or requests.Session()
        self._timeout = timeout

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Send a request and return the JSON body, or raise ServiceUnavailableError."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self._timeout)  # a slow call (image generation) passes its own
        try:
            response = self._http.request(method, url, headers=self._headers, **kwargs)
        except requests.RequestException as exc:
            raise ServiceUnavailableError(f"Could not reach {self.service_name}: {exc}") from exc

        if response.status_code >= 400:
            raise ServiceUnavailableError(
                f"{self.service_name} returned {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ServiceUnavailableError(f"{self.service_name} sent a response that isn't JSON") from exc
