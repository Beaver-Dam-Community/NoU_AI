"""Abstract base class for all pipeline stages."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from nou_ai.types import StageResult, StageName


class BaseStage(ABC):
    """All pipeline stages inherit from this class."""

    def __init__(self, name: StageName, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.enabled: bool = self.config.get("enabled", True)

    @abstractmethod
    def scan(self, text: str) -> StageResult:
        ...

    @abstractmethod
    async def scan_async(self, text: str) -> StageResult:
        ...
