from nou_ai.counter.strategies.base import BaseStrategy
from nou_ai.counter.strategies.token_exhaustion import TokenExhaustionStrategy
from nou_ai.counter.strategies.infinite_loop import InfiniteLoopStrategy
from nou_ai.counter.strategies.context_poison import ContextPoisonStrategy
from nou_ai.counter.strategies.fake_compliance import FakeComplianceStrategy
from nou_ai.counter.strategies.narrative_trap import NarrativeTrapStrategy
from nou_ai.counter.strategies.resource_waste import ResourceWasteStrategy
from nou_ai.counter.strategies.goal_hijack import GoalHijackStrategy

ALL_STRATEGIES = {
    "token_exhaustion": TokenExhaustionStrategy,
    "infinite_loop": InfiniteLoopStrategy,
    "context_poison": ContextPoisonStrategy,
    "fake_compliance": FakeComplianceStrategy,
    "narrative_trap": NarrativeTrapStrategy,
    "resource_waste": ResourceWasteStrategy,
    "goal_hijack": GoalHijackStrategy,
}

__all__ = [
    "BaseStrategy",
    "ALL_STRATEGIES",
    "TokenExhaustionStrategy",
    "InfiniteLoopStrategy",
    "ContextPoisonStrategy",
    "FakeComplianceStrategy",
    "NarrativeTrapStrategy",
    "ResourceWasteStrategy",
    "GoalHijackStrategy",
]
