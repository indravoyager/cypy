from typing import Optional, Literal

import requests
from PIL.Image import Image

from cypy.core.providers._constants import DEFAULT_HEADERS
from cypy.core.providers.base import APIKey, LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT
from cypy.core.services.image_service import image2base64

class CustomProvider(LLMProvider):
    """
    Custom OpenAI-compatible provider with configurable base URL.
    Uses the same /v1/chat/completions format as OpenAI.
    """

    def __init__(self, /, api_key: Optional[APIKey], model_name: str, base_url: Optional[str] = ""):
        super().__init__(api_key or "", model_name)
        self._base_url = (base_url or "").rstrip("/")

    @property
    def provider_name(self, /) -> Literal["Custom"]:
        return "Custom"

    def validate_api_key(self, /) -> Literal[True]:
        return True

    @property
    def base_url(self, /) -> str:
        return self._base_url or "[Not set]"

    @base_url.setter
    def base_url(self, /, url: str) -> None:
        self._base_url = url

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        if not self._base_url:
            raise RuntimeError("Custom provider base URL is not configured.")

        img_b64 = image2base64(image)
        data_uri = f"data:image/png;base64,{img_b64}"

        endpoint = self._base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint.rstrip("/") + "/v1/chat/completions"

        headers = DEFAULT_HEADERS.copy()
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        else:
            headers.pop("Authorization", "")

        payload = {
            "model": self.model_name,
            "temperature": 0,
            "top_p": 0.1,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code in (401, 402):
            raise ProviderError

        if response.status_code != 200:
            self._resolve_error(self.provider_name, response)

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Custom response format: {e}")
