from .claude import ClaudeClient
from .openai import OpenAIClient
from .base import BaseLLMClient

PROVIDERS = {
    "claude": ClaudeClient,
    "openai": OpenAIClient,
}

def get_llm_client(provider: str) -> BaseLLMClient:
    provider = provider.lower().strip()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(PROVIDERS.keys())}")
    return PROVIDERS[provider]()