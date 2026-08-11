from typing import Literal, Optional

import requests
from PIL.Image import Image

from cypy.core.providers._constants import DEFAULT_HEADERS
from cypy.core.providers.base import LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT
from cypy.core.services.image_service import image2base64

class OpenCodeGoProvider(LLMProvider):
    """
    OpenCode Go provider (opencode.ai) — OpenAI-compatible API with API key.
    Docs: https://opencode.ai/docs
    """

    BASE_URL = "https://opencode.ai/zen/go/v1/chat/completions"

    @property
    def provider_name(self, /) -> Literal["OpenCode Go"]:
        return "OpenCode Go"

    def validate_api_key(self, /) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        img_b64 = image2base64(image)
        data_uri = f"data:image/png;base64,{img_b64}"

        headers = DEFAULT_HEADERS.copy()
        headers["Authorization"] = f"Bearer {self.api_key}"

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
            raise RuntimeError(f"OpenCode Go API error {response.status_code}: {detail}")

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenCode Go response format: {e}")
