"""Client for LiteLLM/OpenAI-compatible gateways."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None


@dataclass(frozen=True)
class GatewayModel:
    """Model metadata exposed by a gateway."""

    id: str
    name: str
    owned_by: Optional[str] = None


class LiteLLMClient:
    """Thin client for OpenAI-compatible gateway endpoints."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        if not base_url:
            raise ValueError("base_url is required for LiteLLM client")
        if OpenAI is None:
            raise ImportError("LiteLLM client requires 'openai' library.")

        self.base_url = self._normalize_base_url(base_url)
        self.api_key = api_key or "sk-placeholder"
        self._http_client = self._build_http_client()
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=self._http_client,
        )

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)
        if not parsed.path:
            return f"{normalized}/v1"
        return normalized

    @staticmethod
    def _build_http_client() -> httpx.Client:
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0)
        return httpx.Client(http2=True, timeout=timeout, follow_redirects=True)

    def list_models(self) -> list[GatewayModel]:
        response = self._client.models.list()
        models: list[GatewayModel] = []
        for model in getattr(response, "data", []) or []:
            models.append(
                GatewayModel(
                    id=model.id,
                    name=model.id,
                    owned_by=getattr(model, "owned_by", None),
                )
            )
        return models

    def test_connection(self, model: Optional[str] = None) -> bool:
        if model:
            self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True

        self.list_models()
        return True
