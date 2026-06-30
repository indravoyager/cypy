import io
import base64

import requests

from cypy.core.providers.base import LLMProvider


class ZenProvider(LLMProvider):
    """
    Zen provider (opencode.ai) — OpenAI-compatible API, no key required.
    Docs: https://opencode.ai/docs/zen/#endpoints
    """

    BASE_URL = "https://opencode.ai/zen/v1/chat/completions"

    @property
    def provider_name(self):
        return "Zen (opencode.ai)"

    def validate_api_key(self):
        """Zen works without an API key — always pass validation."""
        return True

    def translate_image(self, image, prompt):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{img_b64}"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
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

        response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=120)

        if response.status_code == 401:
            raise ValueError("API_KEY_ERROR")

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