import anthropic
from .base import BaseLLMClient, LLMResponse
from app.config import CLAUDE_API_KEY

class ClaudeClient(BaseLLMClient):
    def __init__(self, model="claude-sonnet-4-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
        self.model = model

    async def complete(self, prompt: str, system=None, **kwargs):
        print(f"ClaudeClient: Completing with model '{self.model}'")

        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=18096,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )

        return msg.content[0].text