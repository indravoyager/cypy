from typing import Literal, Optional
from PIL.Image import Image

from cypy.core.providers.base import LLMProvider, ProviderError
from cypy.core.config import REQUEST_TIMEOUT

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider using the google-genai SDK.
    """

    @property
    def provider_name(self, /) -> Literal["Google Gemini"]:
        return "Google Gemini"

    def translate_image(self, /, image: Image, prompt: str) -> Optional[str]:
        if genai is None:
            raise ImportError(
                "google-genai package is not installed. "
                "Install it with: pip install google-genai"
            )

        client = genai.Client(api_key=self.api_key)
        model_config = {
            "temperature": 0,
            "top_p": 0.1,
            "top_k": 1,
            "response_mime_type": "application/json",
            "http_options": {
                "timeout": REQUEST_TIMEOUT * 1000  # in milliseconds
            }
        }

        if types is not None:
            retries = 2
            while retries > 0:
                if retries == 2:
                    used_config = types.GenerateContentConfig(**model_config)
                else:
                    fallback_dict = model_config.copy()
                    fallback_dict["response_mime_type"] = None
                    used_config = types.GenerateContentConfig(**fallback_dict)

                retries -= 1

                try:
                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=[image, prompt],
                        config=used_config
                    )
                    return response.text
                except Exception as e:
                    self._check_api_key_error(e)
                    if retries > 0:
                        continue
                    raise e

        # Final fallback without types
        retries = 2
        while retries > 0:
            if retries == 2:
                used_config = model_config
            else:
                fallback_dict = model_config.copy()
                fallback_dict["response_mime_type"] = None
                used_config = fallback_dict

            retries -= 1

            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[image, prompt],
                    config=used_config  # type: ignore
                )
                return response.text
            except Exception as e:
                self._check_api_key_error(e)
                if retries > 0:
                    continue
                raise e

    @staticmethod
    def _check_api_key_error(err: Exception) -> None:
        """Check if an error is related to API key issues and raise `ValueError` if so."""
        err_str = str(err).lower()
        if any(keyword in err_str for keyword in [
            "api key expired", "api_key_invalid", "api key", "api_key"
        ]):
            raise ProviderError
