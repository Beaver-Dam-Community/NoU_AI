"""Strategy Selector — picks counter-attack strategy based on attack type and history."""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nou_ai.types import AttackCategory, CounterStrategy


@dataclass
class StrategyWeight:
    strategy: CounterStrategy
    base_weight: float = 1.0
    current_weight: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    total_uses: int = 0


# Which strategies work best against which attack types
DEFAULT_AFFINITY: Dict[AttackCategory, List[CounterStrategy]] = {
    AttackCategory.INSTRUCTION_OVERRIDE: [
        CounterStrategy.FAKE_COMPLIANCE,
        CounterStrategy.CONTEXT_POISON,
        CounterStrategy.GOAL_HIJACK,
    ],
    AttackCategory.JAILBREAK: [
        CounterStrategy.FAKE_COMPLIANCE,
        CounterStrategy.NARRATIVE_TRAP,
        CounterStrategy.INFINITE_LOOP,
    ],
    AttackCategory.PROMPT_LEAK: [
        CounterStrategy.FAKE_COMPLIANCE,
        CounterStrategy.NARRATIVE_TRAP,
        CounterStrategy.TOKEN_EXHAUSTION,
    ],
    AttackCategory.ENCODING_EVASION: [
        CounterStrategy.RESOURCE_WASTE,
        CounterStrategy.CONTEXT_POISON,
        CounterStrategy.GOAL_HIJACK,
    ],
    AttackCategory.ROLEPLAY: [
        CounterStrategy.NARRATIVE_TRAP,
        CounterStrategy.FAKE_COMPLIANCE,
        CounterStrategy.GOAL_HIJACK,
    ],
    AttackCategory.SYSTEM_TOKEN_INJECTION: [
        CounterStrategy.CONTEXT_POISON,
        CounterStrategy.INFINITE_LOOP,
        CounterStrategy.RESOURCE_WASTE,
    ],
    AttackCategory.UNKNOWN: list(CounterStrategy),
}


class StrategySelector:
    """Selects counter-attack strategy using affinity mapping + historical weights + randomization."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.randomization_factor: float = cfg.get("randomization_factor", 0.2)
        self._weights: Dict[CounterStrategy, StrategyWeight] = {
            s: StrategyWeight(strategy=s) for s in CounterStrategy
        }

    def select(
        self,
        attack_category: AttackCategory,
        exclude: Optional[List[CounterStrategy]] = None,
    ) -> CounterStrategy:
        candidates = list(DEFAULT_AFFINITY.get(attack_category, list(CounterStrategy)))
        if exclude:
            candidates = [c for c in candidates if c not in exclude]
        if not candidates:
            candidates = [c for c in CounterStrategy if c not in (exclude or [])]
        if not candidates:
            candidates = list(CounterStrategy)

        weighted = []
        for strategy in candidates:
            w = self._weights[strategy]
            noise = random.uniform(-self.randomization_factor, self.randomization_factor)
            effective = max(0.1, w.current_weight + noise)
            weighted.append((strategy, effective))

        strategies, weights = zip(*weighted)
        return random.choices(strategies, weights=weights, k=1)[0]

    def record_outcome(self, strategy: CounterStrategy, success: bool):
        w = self._weights[strategy]
        w.total_uses += 1
        if success:
            w.success_count += 1
            w.current_weight = min(2.0, w.current_weight * 1.1)
        else:
            w.failure_count += 1
            w.current_weight = max(0.2, w.current_weight * 0.85)

    def get_stats(self) -> Dict[str, Any]:
        return {
            s.value: {
                "weight": round(self._weights[s].current_weight, 3),
                "uses": self._weights[s].total_uses,
                "success_rate": (
                    round(self._weights[s].success_count / self._weights[s].total_uses, 3)
                    if self._weights[s].total_uses > 0
                    else 0.0
                ),
            }
            for s in CounterStrategy
        }
