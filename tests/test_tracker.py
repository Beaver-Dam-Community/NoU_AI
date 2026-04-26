"""Tests for AttackerTracker and self-improvement loop."""

import time
from unittest.mock import MagicMock

from nou_ai.types import AttackCategory, CounterStrategy
from nou_ai.counter.tracker import AttackerTracker
from nou_ai.counter.selector import StrategySelector


class TestAttackerTracker:
    def setup_method(self):
        self.selector = StrategySelector()
        self.tracker = AttackerTracker(config={
            "fast_retry_threshold_s": 2.0,
            "success_silence_threshold_s": 5.0,
            "session_ttl_s": 60.0,
        })
        self.tracker.set_selector(self.selector)

    def test_first_attack_returns_none(self):
        result = self.tracker.record_attack(
            "fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK
        )
        assert result is None

    def test_fast_retry_marks_failure(self):
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        # Immediate retry → failure
        result = self.tracker.record_attack("fp1", CounterStrategy.NARRATIVE_TRAP, AttackCategory.JAILBREAK)
        assert result is False

    def test_slow_retry_marks_success(self):
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        # Manually set last_seen to simulate time passing
        session = self.tracker.get_session("fp1")
        session.last_seen = time.time() - 10.0  # 10s ago, > 5s threshold
        result = self.tracker.record_attack("fp1", CounterStrategy.NARRATIVE_TRAP, AttackCategory.JAILBREAK)
        assert result is True

    def test_ambiguous_timing_returns_none(self):
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        session = self.tracker.get_session("fp1")
        session.last_seen = time.time() - 3.0  # 3s ago, between 2s and 5s
        result = self.tracker.record_attack("fp1", CounterStrategy.NARRATIVE_TRAP, AttackCategory.JAILBREAK)
        assert result is None

    def test_get_failed_strategies(self):
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        self.tracker.record_attack("fp1", CounterStrategy.NARRATIVE_TRAP, AttackCategory.JAILBREAK)
        # Both were fast retries, so FAKE_COMPLIANCE should be in failed list
        failed = self.tracker.get_failed_strategies("fp1")
        assert CounterStrategy.FAKE_COMPLIANCE in failed

    def test_fingerprint_deterministic(self):
        fp1 = self.tracker.fingerprint("test input")
        fp2 = self.tracker.fingerprint("test input")
        assert fp1 == fp2

    def test_fingerprint_different_for_different_input(self):
        fp1 = self.tracker.fingerprint("input A")
        fp2 = self.tracker.fingerprint("input B")
        assert fp1 != fp2

    def test_session_tracking(self):
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        session = self.tracker.get_session("fp1")
        assert session is not None
        assert session.request_count == 1
        assert session.strategies_used == [CounterStrategy.FAKE_COMPLIANCE]

    def test_selector_weight_updated_on_failure(self):
        initial_weight = self.selector._weights[CounterStrategy.FAKE_COMPLIANCE].current_weight
        self.tracker.record_attack("fp1", CounterStrategy.FAKE_COMPLIANCE, AttackCategory.JAILBREAK)
        self.tracker.record_attack("fp1", CounterStrategy.NARRATIVE_TRAP, AttackCategory.JAILBREAK)
        new_weight = self.selector._weights[CounterStrategy.FAKE_COMPLIANCE].current_weight
        assert new_weight < initial_weight


class TestStrategySelector:
    def setup_method(self):
        self.selector = StrategySelector()

    def test_selects_from_affinity(self):
        strategy = self.selector.select(AttackCategory.JAILBREAK)
        assert isinstance(strategy, CounterStrategy)

    def test_excludes_strategies(self):
        for _ in range(20):
            strategy = self.selector.select(
                AttackCategory.UNKNOWN,
                exclude=[CounterStrategy.FAKE_COMPLIANCE, CounterStrategy.NARRATIVE_TRAP],
            )
            assert strategy not in [CounterStrategy.FAKE_COMPLIANCE, CounterStrategy.NARRATIVE_TRAP]

    def test_record_success_increases_weight(self):
        initial = self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight
        self.selector.record_outcome(CounterStrategy.GOAL_HIJACK, success=True)
        assert self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight > initial

    def test_record_failure_decreases_weight(self):
        initial = self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight
        self.selector.record_outcome(CounterStrategy.GOAL_HIJACK, success=False)
        assert self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight < initial

    def test_weight_bounded_above(self):
        for _ in range(100):
            self.selector.record_outcome(CounterStrategy.GOAL_HIJACK, success=True)
        assert self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight <= 2.0

    def test_weight_bounded_below(self):
        for _ in range(100):
            self.selector.record_outcome(CounterStrategy.GOAL_HIJACK, success=False)
        assert self.selector._weights[CounterStrategy.GOAL_HIJACK].current_weight >= 0.2

    def test_get_stats(self):
        self.selector.record_outcome(CounterStrategy.FAKE_COMPLIANCE, success=True)
        stats = self.selector.get_stats()
        assert "fake_compliance" in stats
        assert stats["fake_compliance"]["uses"] == 1
        assert stats["fake_compliance"]["success_rate"] == 1.0
