from typing import Literal, Optional

import requests
from PIL.Image import Image

from cypy.core.providers._constants import DEFAULT_HEADERS
from cypy.core.providers.base import LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT
from cypy.core.services.image_service import image2base64

class OpenAIProvider(LLMProvider):
    """
    OpenAI provider using the REST API directly.
    Supports GPT-5.4, GPT-5.4-mini, and other vision-capable models.
    Uses only `requests` — no extra SDK needed~ ♪

    Get your API key at: https://platform.openai.com/api-keys
    """

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def provider_name(self, /) -> Literal["OpenAI"]:
        return "OpenAI"

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        img_base64 = image2base64(image)
        data_uri = f"data:image/png;base64,{img_base64}"

        if not self.validate_api_key():
            raise ProviderError

        headers = DEFAULT_HEADERS.copy()
        headers["Authorization"] = f"Bearer {self.api_key.strip()}"

        payload = {
            "model": self.model_name,
            "temperature": 0,
            "top_p": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri, "detail": "high"},
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        }

        response = requests.post(
            self.BASE_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 401:
            raise ProviderError

        if response.status_code != 200:
            self._resolve_error(self.provider_name, response)

        result = response.json()

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenAI response format: {e}")

        return content
