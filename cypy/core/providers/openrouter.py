from typing import Literal, Optional

import requests
from PIL.Image import Image

from cypy.core.providers._constants import DEFAULT_HEADERS
from cypy.core.providers.base import LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT
from cypy.core.services.image_service import image2base64

class OpenRouterProvider(LLMProvider):
    """
    OpenRouter provider using the OpenAI-compatible REST API.
    Supports hundreds of models including Claude, Llama, Mistral, Gemini, etc.
    Uses only `requests` — no extra SDK needed~ ♪

    Get your API key at: https://openrouter.ai/keys
    Browse models at: https://openrouter.ai/models
    """

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def provider_name(self, /) -> Literal["OpenRouter"]:
        return "OpenRouter"

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        img_base64 = image2base64(image)
        data_uri = f"data:image/png;base64,{img_base64}"

        if not self.validate_api_key():
            raise ProviderError

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
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
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

        if response.status_code in (401, 402):
            raise ProviderError

        if response.status_code != 200:
            self._resolve_error(self.provider_name, response)

        result = response.json()

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenRouter response format: {e}")

        return content
