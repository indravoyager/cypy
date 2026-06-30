from cypy.core.providers.base import LLMProvider
from cypy.core.providers.gemini import GeminiProvider
from cypy.core.providers.openrouter import OpenRouterProvider
from cypy.core.providers.openai_provider import OpenAIProvider
from cypy.core.providers.zen import ZenProvider
from cypy.core.providers.custom import CustomProvider

PROVIDER_MAP = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "zen": ZenProvider,
    "openrouter": OpenRouterProvider,
    "custom": CustomProvider,
}


def create_provider(provider_name, api_key, model_name, **kwargs):
    cls = PROVIDER_MAP.get(provider_name)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider_name}")
    return cls(api_key=api_key, model_name=model_name, **kwargs)
