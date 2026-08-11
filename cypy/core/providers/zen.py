from typing import Literal, Optional

import requests
from PIL.Image import Image

from cypy.core.providers._constants import DEFAULT_HEADERS
from cypy.core.providers.base import LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT
from cypy.core.services.image_service import image2base64

class ZenProvider(LLMProvider):
    """
    Zen provider (opencode.ai) — OpenAI-compatible API, no key required.
    Docs: https://opencode.ai/docs/zen/#endpoints
    """

    BASE_URL = "https://opencode.ai/zen/v1/chat/completions"

    @property
    def provider_name(self, /) -> Literal["Zen (opencode.ai)"]:
        return "Zen (opencode.ai)"

    def validate_api_key(self, /) -> Literal[True]:
        """Zen works without an API key — always pass validation."""
        return True

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        img_b64 = image2base64(image)
        data_uri = f"data:image/png;base64,{img_b64}"

        headers = DEFAULT_HEADERS.copy()
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
            self.BASE_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 401:
            raise ProviderError

        if response.status_code != 200:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:200]
            raise RuntimeError(f"Zen API error {response.status_code}: {detail}")

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Zen response format: {e}")
