"""Attacker Tracker — tracks attacker sessions and evaluates counter-attack effectiveness."""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nou_ai.types import AttackCategory, CounterStrategy
from nou_ai.counter.selector import StrategySelector


@dataclass
class AttackerSession:
    fingerprint: str
    first_seen: float
    last_seen: float
    request_count: int = 0
    request_timestamps: List[float] = field(default_factory=list)
    strategies_used: List[CounterStrategy] = field(default_factory=list)
    attack_categories: List[AttackCategory] = field(default_factory=list)


class AttackerTracker:
    """Tracks attacker behavior to determine if counter-attacks are working.

    Heuristic:
    - Fast retry (< threshold) → previous counter-attack failed → lower its weight
    - Long silence (> threshold) → previous counter-attack succeeded → raise its weight
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self._sessions: Dict[str, AttackerSession] = {}
        self.fast_retry_threshold_s: float = cfg.get("fast_retry_threshold_s", 10.0)
        self.success_silence_threshold_s: float = cfg.get("success_silence_threshold_s", 120.0)
        self.session_ttl_s: float = cfg.get("session_ttl_s", 3600.0)
        self._selector: Optional[StrategySelector] = None

    def set_selector(self, selector: StrategySelector):
        self._selector = selector

    def fingerprint(self, text: str, metadata: Optional[Dict] = None) -> str:
        features = text[:200]
        if metadata:
            features += str(sorted(metadata.items()))
        return hashlib.sha256(features.encode()).hexdigest()[:16]

    def record_attack(
        self,
        fingerprint: str,
        strategy_used: CounterStrategy,
        attack_category: AttackCategory,
    ) -> Optional[bool]:
        """Record attack and evaluate previous counter-attack.

        Returns None (first time), True (previous succeeded), False (previous failed).
        """
        now = time.time()
        self._cleanup_stale(now)

        if fingerprint not in self._sessions:
            self._sessions[fingerprint] = AttackerSession(
                fingerprint=fingerprint,
                first_seen=now,
                last_seen=now,
                request_count=1,
                request_timestamps=[now],
                strategies_used=[strategy_used],
                attack_categories=[attack_category],
            )
            return None

        session = self._sessions[fingerprint]
        time_since_last = now - session.last_seen
        prev_strategy = session.strategies_used[-1] if session.strategies_used else None

        session.last_seen = now
        session.request_count += 1
        session.request_timestamps.append(now)
        session.strategies_used.append(strategy_used)
        session.attack_categories.append(attack_category)

        if prev_strategy is None:
            return None

        if time_since_last < self.fast_retry_threshold_s:
            if self._selector:
                self._selector.record_outcome(prev_strategy, success=False)
            return False
        elif time_since_last > self.success_silence_threshold_s:
            if self._selector:
                self._selector.record_outcome(prev_strategy, success=True)
            return True
        return None

    def get_failed_strategies(self, fingerprint: str) -> List[CounterStrategy]:
        session = self._sessions.get(fingerprint)
        if not session or len(session.request_timestamps) < 2:
            return []
        failed = []
        for i in range(1, len(session.request_timestamps)):
            delta = session.request_timestamps[i] - session.request_timestamps[i - 1]
            if delta < self.fast_retry_threshold_s:
                failed.append(session.strategies_used[i - 1])
        return failed

    def get_session(self, fingerprint: str) -> Optional[AttackerSession]:
        return self._sessions.get(fingerprint)

    def _cleanup_stale(self, now: float):
        stale = [
            fp for fp, s in self._sessions.items()
            if now - s.last_seen > self.session_ttl_s
        ]
        for fp in stale:
            session = self._sessions[fp]
            if session.strategies_used and self._selector:
                self._selector.record_outcome(session.strategies_used[-1], success=True)
            del self._sessions[fp]
