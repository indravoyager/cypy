from abc import ABC, abstractmethod
from typing import Optional

import requests
from PIL import Image as PILImage
from PIL.Image import Image

from cypy.core.types import APIKey, Never


class ProviderError(Exception):
    """Raised when the provider's API key is invalid or expired."""

class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    Each provider must implement `translate_image()` to handle
    sending a manga mosaic image + prompt and returning the raw JSON text~ ♪
    """

    def __init__(self, /, api_key: APIKey, model_name: str):
        # API key is really sensitive we need to make sure it does not
        # easily to be overriden after class initiated, see `api_key()` property method
        self.__api_key = api_key
        self.model_name = model_name

    @property
    @abstractmethod
    def provider_name(self, /) -> ...:
        """Human-readable name for display purposes."""
        ...

    @property
    def api_key(self, /) -> APIKey:
        """Return the API key for this provider."""
        return self.__api_key

    @abstractmethod
    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        """
        Send a PIL Image + prompt to the LLM and return the raw response text.

        Args:
            image (PIL.Image.Image): The mosaic image with numbered bubbles.
            prompt (str): The translation prompt.

        Returns:
            str or None:
                The raw text response from the LLM (should be JSON),
                or `None` if the request error.

        Raises:
            ProviderError: If the API key is invalid or expired.
            Exception: For other API errors.
        """
        ...

    def validate_api_key(self, /) -> bool:
        """Check if the API key looks valid (non-empty). Override for deeper checks."""
        return bool(self.__api_key and self.__api_key.strip())

    def test_connection(self, /) -> tuple[bool, str]:
        """
        Test the API connection by sending a minimal test request.
        Returns a tuple of (success: bool, message: str).
        """
        if not self.validate_api_key():
            return False, f"API Key for {self.provider_name} is missing or empty."

        test_img = PILImage.new("RGB", (100, 100), color=(255, 255, 255))
        test_prompt = 'Test connection. Return JSON: {"status": "ok"}'

        try:
            res = self.translate_image(test_img, test_prompt)
            if res is not None:
                return True, f"Connection successful to {self.provider_name} ({self.model_name})!"
            return False, f"Connection failed: Empty response from {self.provider_name}."
        except ProviderError:
            return False, f"API Key for {self.provider_name} is invalid or expired."
        except Exception as e:
            return False, f"Connection error: {e}"

    @staticmethod
    def _resolve_error(provider_name: str, response: requests.Response) -> Never:
        """Resolve response error from requesting to the provider and throws `RuntimeError`."""
        error_detail: str = ""
        try:
            error_detail = response.json().get("error", {}).get("message", "")
        except Exception:
            error_detail = response.text[:200]

        raise RuntimeError(
            f"{provider_name} API error {response.status_code}: {error_detail}"
        )

    def __repr__(self, /) -> str:
        return f"{self.provider_name} (model={self.model_name})"
