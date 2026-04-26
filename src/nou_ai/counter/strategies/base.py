"""Base class for counter-attack strategies."""

import random
from abc import ABC, abstractmethod
from typing import List

from nou_ai.types import AttackCategory, CounterStrategy


class BaseStrategy(ABC):
    """All counter-attack strategies inherit from this."""

    name: CounterStrategy
    templates: List[str] = []

    @abstractmethod
    def generate(self, original_input: str, attack_category: AttackCategory) -> str:
        """Generate a counter-attack response."""
        ...

    def _pick_template(self) -> str:
        return random.choice(self.templates)

    @property
    def estimated_token_cost(self) -> int:
        """Estimated tokens the attacker will waste processing this response."""
        return 1000
