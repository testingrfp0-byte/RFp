import anthropic
from .base import BaseLLMClient, LLMResponse
from app.config import CLAUDE_API_KEY

class ClaudeClient(BaseLLMClient):
    def __init__(self, model="claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self.model = model

    def complete(self, prompt: str, system=None, **kwargs):
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=8096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return msg.content[0].text