from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str

class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None):
        pass