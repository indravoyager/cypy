import io
import base64

from cypy.core.providers.base import LLMProvider

try:
    import requests
except ImportError:
    requests = None


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider using the REST API directly.
    Supports GPT-5.4, GPT-5.4-mini, and other vision-capable models.
    Uses only `requests` — no extra SDK needed~ ♪

    Get your API key at: https://platform.openai.com/api-keys
    """

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def provider_name(self):
        return "OpenAI"

    def translate_image(self, image, prompt):
        if requests is None:
            raise ImportError(
                "requests package is not installed. "
                "Install it with: pip install requests"
            )

        # Convert PIL Image to base64 data URI
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        data_uri = f"data:image/png;base64,{img_base64}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
            timeout=120,
        )

        if response.status_code == 401:
            raise ValueError("API_KEY_ERROR")

        if response.status_code != 200:
            error_detail = ""
            try:
                error_detail = response.json().get("error", {}).get("message", "")
            except Exception:
                error_detail = response.text[:200]
            raise RuntimeError(
                f"OpenAI API error {response.status_code}: {error_detail}"
            )

        result = response.json()

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenAI response format: {e}")

        return content
