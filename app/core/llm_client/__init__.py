from .claude import ClaudeClient
from .openai import OpenAIClient
from .base import BaseLLMClient

PROVIDERS = {
    "claude": ClaudeClient,
    "openai": OpenAIClient,
}

MODEL_REGISTRY = {
    "gpt-4o": {"provider": "openai"},
    "gpt-4o-mini": {"provider": "openai"},
    "gpt-5.4": {"provider": "openai"},
    "claude-sonnet-4-6": {"provider": "claude"},
    "claude-opus-4-6": {"provider": "claude"},
    "claude-haiku-4-5-20251001": {"provider": "claude"},
}

# def get_llm_client(provider: str, model: str = None) -> BaseLLMClient:
#     provider = provider.lower().strip()
#     if provider not in PROVIDERS:
#         raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(PROVIDERS.keys())}")
#     return PROVIDERS[provider](model=model)


def get_llm_client(model: str) -> BaseLLMClient:
    model = model.lower().strip()
    # print(f"Requested LLM model: '{model}'")

    if model not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model '{model}'. Supported: {list(MODEL_REGISTRY.keys())}")

    provider_name = MODEL_REGISTRY[model]["provider"]

    if provider_name not in PROVIDERS:
        raise ValueError(f"Provider '{provider_name}' not configured")

    client_class = PROVIDERS[provider_name]

    return client_class(model=model)
