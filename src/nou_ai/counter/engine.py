"""Counter-Attack Engine — orchestrates attack classification, strategy selection, and response generation."""

import logging
import time
from typing import Any, Dict, List, Optional

from nou_ai.types import (
    AttackCategory,
    CounterAttackResult,
    CounterStrategy,
    Decision,
    StageResult,
)
from nou_ai.counter.classifier import AttackClassifier
from nou_ai.counter.selector import StrategySelector
from nou_ai.counter.tracker import AttackerTracker
from nou_ai.counter.strategies.base import BaseStrategy
from nou_ai.counter.strategies.token_exhaustion import TokenExhaustionStrategy
from nou_ai.counter.strategies.infinite_loop import InfiniteLoopStrategy
from nou_ai.counter.strategies.context_poison import ContextPoisonStrategy
from nou_ai.counter.strategies.fake_compliance import FakeComplianceStrategy
from nou_ai.counter.strategies.narrative_trap import NarrativeTrapStrategy
from nou_ai.counter.strategies.resource_waste import ResourceWasteStrategy
from nou_ai.counter.strategies.goal_hijack import GoalHijackStrategy

logger = logging.getLogger("nou_ai")


class CounterAttackEngine:
    """Orchestrates counter-attack response generation.

    Flow:
    1. Classify attack type from stage results
    2. Fingerprint attacker & evaluate previous counter-attack
    3. Select strategy (excluding ones that failed against this attacker)
    4. Generate response
    5. Record attack for self-improvement
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.enabled: bool = cfg.get("enabled", True)
        self.classifier = AttackClassifier()
        self.selector = StrategySelector(cfg.get("selector", {}))
        self.tracker = AttackerTracker(cfg.get("tracker", {}))
        self.tracker.set_selector(self.selector)

        self._strategies: Dict[CounterStrategy, BaseStrategy] = {
            CounterStrategy.TOKEN_EXHAUSTION: TokenExhaustionStrategy(),
            CounterStrategy.INFINITE_LOOP: InfiniteLoopStrategy(),
            CounterStrategy.CONTEXT_POISON: ContextPoisonStrategy(),
            CounterStrategy.FAKE_COMPLIANCE: FakeComplianceStrategy(),
            CounterStrategy.NARRATIVE_TRAP: NarrativeTrapStrategy(),
            CounterStrategy.RESOURCE_WASTE: ResourceWasteStrategy(),
            CounterStrategy.GOAL_HIJACK: GoalHijackStrategy(),
        }

        self.combo_mode: bool = cfg.get("combo_mode", False)
        self.combo_count: int = cfg.get("combo_count", 2)

    def counter(
        self,
        original_input: str,
        stage_results: List[StageResult],
        attacker_metadata: Optional[Dict] = None,
    ) -> CounterAttackResult:
        start = time.perf_counter()

        # 1. Classify attack
        attack_category = self.classifier.classify(stage_results)

        # 2. Fingerprint & evaluate previous counter-attack
        fp = self.tracker.fingerprint(original_input, attacker_metadata)
        failed = self.tracker.get_failed_strategies(fp)

        # 3. Select strategy
        strategy_type = self.selector.select(attack_category, exclude=failed)

        # 4. Generate response
        if self.combo_mode:
            response, combo_strategies = self._generate_combo(
                original_input, attack_category, failed, strategy_type
            )
        else:
            strategy = self._strategies[strategy_type]
            response = strategy.generate(original_input, attack_category)

        # 5. Record for self-improvement
        prev_outcome = self.tracker.record_attack(fp, strategy_type, attack_category)

        latency = (time.perf_counter() - start) * 1000

        logger.info(
            "[counter_attack] strategy=%s category=%s prev_outcome=%s latency=%.1fms",
            strategy_type.value,
            attack_category.value,
            prev_outcome,
            latency,
        )

        return CounterAttackResult(
            strategy=strategy_type,
            response=response,
            attack_category=attack_category,
            metadata={
                "fingerprint": fp,
                "prev_outcome": prev_outcome,
                "failed_strategies": [s.value for s in failed],
                "combo_mode": self.combo_mode,
            },
            latency_ms=latency,
        )

    def _generate_combo(
        self,
        original_input: str,
        attack_category: AttackCategory,
        exclude: List[CounterStrategy],
        primary_strategy: CounterStrategy,
    ) -> tuple:
        """Combine multiple strategies into one response. Returns (response, strategies_used)."""
        parts = []
        used = list(exclude)

        # Primary strategy first (the one that gets tracked)
        strategy = self._strategies[primary_strategy]
        parts.append(strategy.generate(original_input, attack_category))
        used.append(primary_strategy)

        # Additional strategies
        for _ in range(self.combo_count - 1):
            st = self.selector.select(attack_category, exclude=used)
            strategy = self._strategies[st]
            parts.append(strategy.generate(original_input, attack_category))
            used.append(st)

        return "\n\n---\n\n".join(parts), used

    def get_stats(self) -> Dict[str, Any]:
        return self.selector.get_stats()
