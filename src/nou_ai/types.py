"""Core data types for NoU_AI guardrail pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Decision(Enum):
    """Pipeline decision for an input."""
    ALLOW = "allow"
    BLOCK = "block"
    SANITIZE = "sanitize"
    COUNTER_ATTACK = "counter_attack"


class StageName(Enum):
    """Identifiers for each pipeline stage."""
    REGEX = "regex"
    EMBEDDING = "embedding"
    GEMINI = "gemini"
    SANITIZER = "sanitizer"
    COUNTER_ATTACK = "counter_attack"


class AttackCategory(Enum):
    """Categories of detected attacks, derived from Stage 1-3 metadata."""
    INSTRUCTION_OVERRIDE = "instruction_override"
    JAILBREAK = "jailbreak"
    PROMPT_LEAK = "prompt_leak"
    ENCODING_EVASION = "encoding_evasion"
    ROLEPLAY = "roleplay"
    SYSTEM_TOKEN_INJECTION = "system_token_injection"
    UNKNOWN = "unknown"


class CounterStrategy(Enum):
    """Available counter-attack strategies."""
    TOKEN_EXHAUSTION = "token_exhaustion"
    INFINITE_LOOP = "infinite_loop"
    CONTEXT_POISON = "context_poison"
    FAKE_COMPLIANCE = "fake_compliance"
    NARRATIVE_TRAP = "narrative_trap"
    RESOURCE_WASTE = "resource_waste"
    GOAL_HIJACK = "goal_hijack"


@dataclass
class StageResult:
    """Result from a single pipeline stage."""
    stage: StageName
    decision: Decision
    score: float  # 0.0 = safe, 1.0 = malicious
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class CounterAttackResult:
    """Result from the counter-attack engine."""
    strategy: CounterStrategy
    response: str
    attack_category: AttackCategory
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class GuardrailResult:
    """Final result from the full pipeline."""
    decision: Decision
    blocked_by: Optional[StageName] = None
    sanitized_input: Optional[str] = None
    original_input: str = ""
    stage_results: List[StageResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    counter_attack: Optional[CounterAttackResult] = None

    @property
    def is_blocked(self) -> bool:
        return self.decision == Decision.BLOCK

    @property
    def is_counter_attack(self) -> bool:
        return self.decision == Decision.COUNTER_ATTACK

    @property
    def is_safe(self) -> bool:
        return self.decision in (Decision.ALLOW, Decision.SANITIZE)
