import io
import base64

import requests

from cypy.core.providers.base import LLMProvider


class CustomProvider(LLMProvider):
    """
    Custom OpenAI-compatible provider with configurable base URL.
    Uses the same /v1/chat/completions format as OpenAI.
    """

    def __init__(self, api_key, model_name, base_url=""):
        super().__init__(api_key, model_name)
        self._base_url = (base_url or "").rstrip("/")

    @property
    def provider_name(self):
        return "Custom"

    def validate_api_key(self):
        """Key is optional — some local providers don't need one."""
        return True

    @property
    def base_url(self):
        return self._base_url or "Not set"

    def translate_image(self, image, prompt):
        if not self._base_url:
            raise RuntimeError("Custom provider base URL is not configured.")

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{img_b64}"

        # Build endpoint URL — append /chat/completions if not already present
        endpoint = self._base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = endpoint.rstrip("/") + "/v1/chat/completions"

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

        response = requests.post(endpoint, headers=headers, json=payload, timeout=120)

        if response.status_code == 401:
            raise ValueError("API_KEY_ERROR")

        if response.status_code != 200:
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:200]
            raise RuntimeError(f"Custom API error {response.status_code}: {detail}")

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Custom response format: {e}")
